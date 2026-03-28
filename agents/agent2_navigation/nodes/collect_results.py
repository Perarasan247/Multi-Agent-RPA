"""Node: Collect search results from the left panel tree."""

import re
import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def _find_via_screenshot(app, report_name: str) -> dict | None:
    """Locate the report item using screenshot-based detection.

    Tries OpenCV highlight detection first, then Gemini (coordinate-based),
    then Gemini (index-based) when coordinates are ambiguous.

    Returns a synthetic candidate dict with screen coords, or None.
    """
    from vision.highlight_detector import find_all_highlight_coords
    from vision.gemini_verifier import find_item_coordinates_with_gemini
    from config.settings import settings
    import google.generativeai as genai
    import base64
    import cv2

    try:
        screenshot = capture_screen()
    except Exception as exc:
        logger.error("collect_results: could not capture screen: {}", exc)
        return None

    # Use the MAIN Excellon frame for panel bounds.
    # get_main_window() wraps the HWND directly — fast, never hangs.
    panel_left, panel_top, panel_w, panel_h = 0, 0, 310, 800
    try:
        from automation.window_manager import get_main_window
        best_win = get_main_window(app)
        wr = best_win.rectangle()
        panel_left = max(0, wr.left)
        panel_top  = max(0, wr.top)
        panel_w    = max(150, min(350, wr.width() // 4))
        panel_h    = max(400, wr.height() - 60)
        logger.debug(
            "Main frame: ({},{}) {}x{} → panel ({},{}) {}x{}",
            wr.left, wr.top, wr.width(), wr.height(),
            panel_left, panel_top, panel_w, panel_h,
        )
    except Exception as exc:
        logger.debug("Could not get window rect, using defaults: {}", exc)

    # Crop to left panel; skip the top ~80px (search bar) so Gemini doesn't
    # confuse the typed text in the search box with a tree item.
    SEARCH_BAR_SKIP = 80
    img_h, img_w = screenshot.shape[:2]
    x1 = max(0, panel_left)
    y1 = max(0, panel_top + SEARCH_BAR_SKIP)
    x2 = min(img_w, panel_left + panel_w)
    y2 = min(img_h, panel_top + panel_h)
    panel_crop = screenshot[y1:y2, x1:x2] if (x2 > x1 and y2 > y1) else screenshot
    logger.debug(
        "Panel crop (tree): ({},{})→({},{}) = {}x{}px",
        x1, y1, x2, y2, x2 - x1, y2 - y1,
    )

    def _make_candidate(sx: int, sy: int) -> dict:
        return {
            "text": report_name,
            "element": None,
            "rect": None,
            "screen_x": sx,
            "screen_y": sy,
            "tree_path": [report_name],
            "depth": 1,
        }

    def _crop_to_b64(img) -> str | None:
        """Encode a BGR numpy array to base64 PNG for Gemini."""
        try:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ok, buf = cv2.imencode(".png", rgb)
            return base64.b64encode(buf.tobytes()).decode("utf-8") if ok else None
        except Exception:
            return None

    def _gemini_row_ocr(regions: list) -> tuple[int, int] | None:
        """Crop each region's row strip and ask Gemini YES/NO: exact text match?

        Much more reliable than counting items in the full panel — Gemini only
        needs to read one row at a time and answer a binary question.
        """
        if not settings.gemini_api_key:
            return None
        try:
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            img_h, img_w = screenshot.shape[:2]

            for sx, sy, area, w in regions:
                # Crop a tight horizontal strip around this row (±14px vertically)
                ry1 = max(0, sy - 14)
                ry2 = min(img_h, sy + 14)
                rx1 = max(0, panel_left)
                rx2 = min(img_w, panel_left + panel_w)
                row_img = screenshot[ry1:ry2, rx1:rx2]
                if row_img.size == 0:
                    continue
                # Scale up 3× so text is clearly readable
                row_scaled = cv2.resize(row_img, None, fx=3, fy=3,
                                        interpolation=cv2.INTER_LINEAR)
                img_b64 = _crop_to_b64(row_scaled)
                if not img_b64:
                    continue

                prompt = (
                    f"Read the text visible in this image (it is a single row from a "
                    f"Windows navigation tree). "
                    f"Does the text of this row say EXACTLY '{report_name}' "
                    f"(case-insensitive, ignore icons)? "
                    f"Reply ONLY 'YES' or 'NO'."
                )
                image_part = {"mime_type": "image/png", "data": img_b64}
                resp = model.generate_content([prompt, image_part])
                answer = resp.text.strip().upper()
                logger.info(
                    "[Row-OCR] '{}' at ({},{}) → Gemini: '{}'",
                    report_name, sx, sy, answer,
                )
                if "YES" in answer:
                    return sx, sy

        except Exception as exc:
            logger.warning("[Row-OCR] error: {}", exc)
        return None

    def _gemini_pick_by_coords() -> tuple[int, int] | None:
        """Ask Gemini for pixel coords of the exact-match item; validate against panel."""
        coords = find_item_coordinates_with_gemini(
            panel_crop, report_name, panel_offset_x=x1, panel_offset_y=y1,
        )
        if not coords:
            return None
        sx, sy = coords
        if sx < x1 or sx > x2 or sy < y1 or sy > y2:
            logger.warning(
                "[Gemini-coords] ({},{}) outside panel bounds ({},{})→({},{}) — rejected.",
                sx, sy, x1, y1, x2, y2,
            )
            return None
        return sx, sy

    def _gemini_pick_by_index(regions: list) -> tuple[int, int] | None:
        """Ask Gemini which numbered item (1..N top-to-bottom) is the exact match.

        Scales the crop 2× before sending so Gemini can read text clearly.
        Uses the word-count and highlight-pattern clues to disambiguate.
        """
        if not settings.gemini_api_key or panel_crop is None or panel_crop.size == 0:
            return None
        try:
            # Scale up 2× so text is easier to read
            scaled = cv2.resize(panel_crop, None, fx=2, fy=2,
                                interpolation=cv2.INTER_LINEAR)
            img_b64 = _crop_to_b64(scaled)
            if not img_b64:
                return None
            genai.configure(api_key=settings.gemini_api_key)
            n = len(regions)
            n_words = len(report_name.strip().split())
            prompt = (
                f"This image shows a navigation tree panel (zoomed 2×). "
                f"There are {n} highlighted tree item(s), numbered 1 to {n} from TOP to BOTTOM. "
                f"I need the item whose COMPLETE text is EXACTLY '{report_name}' "
                f"({n_words} word(s), case-insensitive). "
                f"\n\nKEY VISUAL CLUE: Search results highlight only the matched words "
                f"in yellow/amber. The EXACT match item has EVERY word highlighted with "
                f"NO plain (unhighlighted) text between them. "
                f"Items that are NOT the exact match have extra words in plain text "
                f"(e.g. 'Purchase INVOICE Statement' — 'INVOICE' appears in plain text "
                f"between the highlighted words; 'Purchase ORDER Statement' — 'ORDER' is plain). "
                f"Look for the item where there is NO gap of unhighlighted text — "
                f"all {n_words} word(s) are continuously highlighted. "
                f"\n\nReply with ONLY the item number (1 to {n}). If unsure, reply '1'."
            )
            model = genai.GenerativeModel("gemini-2.0-flash")
            image_part = {"mime_type": "image/png", "data": img_b64}
            response = model.generate_content([prompt, image_part])
            text = response.text.strip()
            logger.info("[Gemini-index] response for '{}': '{}'", report_name, text)
            m = re.search(r"\b(\d+)\b", text)
            if m:
                idx = int(m.group(1)) - 1  # convert to 0-based
                idx = max(0, min(idx, n - 1))
                sx, sy, _ = regions[idx]
                logger.info(
                    "[Gemini-index] chose item {} → screen ({},{}).", idx + 1, sx, sy,
                )
                return sx, sy
        except Exception as exc:
            logger.warning("[Gemini-index] error: {}", exc)
        return None

    # ── Strategy 1: OpenCV highlight detection ──────────────────────────────
    # Returns (screen_cx, screen_cy, area, highlight_width) per row, top-to-bottom.
    # highlight_width is the key discriminator:
    #   - Exact match: ALL words highlighted → morphological closing merges them
    #     into ONE wide region (e.g. "Purchase Statement" ≈ 100px wide).
    #   - Non-exact match: unhighlighted word in the middle (e.g. "Invoice" or
    #     "Order") cannot be bridged by the kernel → only the FIRST chunk per
    #     row survives deduplication (e.g. just "Purchase" ≈ 40px wide).
    all_regions: list[tuple[int, int, float, int]] = []
    try:
        all_regions = find_all_highlight_coords(
            screenshot, panel_left, panel_top, panel_w, panel_h,
        )
        logger.info("[Agent2] OpenCV found {} highlighted region(s).", len(all_regions))
    except Exception as exc:
        logger.warning("OpenCV detection error: {}", exc)

    if len(all_regions) == 1:
        sx, sy, _, w = all_regions[0]
        logger.info("[Agent2] OpenCV single match at ({}, {}) width={}.", sx, sy, w)
        return _make_candidate(sx, sy)

    if len(all_regions) > 1:
        logger.info(
            "[Agent2] {} highlights — disambiguating for '{}'.",
            len(all_regions), report_name,
        )

        # Step 1: Width-based — widest highlight = exact match (all words merged).
        # This is deterministic and works for middle-word disambiguation
        # (e.g. "Purchase Statement" vs "Purchase Invoice Statement").
        widths = [r[3] for r in all_regions]
        max_w = max(widths)
        min_w = min(widths)
        logger.debug("[Width] region widths: {}", widths)

        if max_w - min_w >= 15:
            # Clear width winner — use it directly without Gemini
            best = max(all_regions, key=lambda r: r[3])
            sx, sy = best[0], best[1]
            logger.info(
                "[Agent2] Width-pick: widest={}px at ({}, {}).", max_w, sx, sy,
            )
            return _make_candidate(sx, sy)

        # Step 2: Widths are similar (e.g. "Sales MIS Report" vs
        # "Sales MIS Report New" — extra word is at END, same highlighted span).
        # OCR each row individually: crop the row strip, ask Gemini YES/NO.
        # This is far more reliable than asking Gemini to count items in the
        # full panel image.
        logger.info(
            "[Agent2] Widths too similar ({}-{}px) — trying per-row OCR.",
            min_w, max_w,
        )
        coords = _gemini_row_ocr(all_regions)
        if coords:
            logger.info("[Agent2] Row-OCR picked ({}, {}).", *coords)
            return _make_candidate(*coords)

        # Step 3: Gemini index on full panel (last resort before median)
        coords = _gemini_pick_by_index(all_regions)
        if coords:
            logger.info("[Agent2] Gemini (index) picked ({}, {}).", *coords)
            return _make_candidate(*coords)

        # Step 4: Median region
        mid = len(all_regions) // 2
        sx, sy, _, _ = all_regions[mid]
        logger.info("[Agent2] All fallbacks failed — using median region #{} at ({}, {}).", mid + 1, sx, sy)
        return _make_candidate(sx, sy)

    # ── Strategy 2: No OpenCV hits → Gemini on panel crop ──────────────────
    coords = _gemini_pick_by_coords()
    if coords:
        logger.info("[Agent2] Gemini (no-opencv) found item at ({}, {}).", *coords)
        return _make_candidate(*coords)

    return None


def collect_results_node(state: GlobalState) -> GlobalState:
    """Locate the search result item after typing the report name."""
    logger.info("[Agent2] Node: collect_results — entering")
    try:
        app = state["app_handle"]
        report_name = state["report_name"]

        time.sleep(1.5)

        candidate = _find_via_screenshot(app, report_name)

        if not candidate:
            state["error"] = (
                f"Could not locate '{report_name}' in the left panel "
                f"via screenshot detection (OpenCV + Gemini)."
            )
            logger.error("[Agent2] {}", state["error"])
            save_debug_screenshot(capture_screen(), "collect_results_failed")
            return state

        state["ui_candidates"] = [candidate]
        logger.info(
            "[Agent2] Candidate found: '{}' at screen ({}, {}).",
            candidate["text"], candidate["screen_x"], candidate["screen_y"],
        )

    except Exception as exc:
        state["error"] = f"collect_results failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "collect_results_error")
        except Exception:
            pass

    return state
