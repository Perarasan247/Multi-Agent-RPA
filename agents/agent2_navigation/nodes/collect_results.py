"""Node: Collect search results from the left panel tree."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def _find_via_screenshot(app, report_name: str) -> dict | None:
    """Locate the report item using screenshot-based detection.

    Tries OpenCV yellow-highlight detection first (no API key needed),
    then falls back to Gemini Vision if a key is configured.

    Returns a synthetic candidate dict with screen coords, or None.
    """
    from vision.highlight_detector import find_all_highlight_coords
    from vision.gemini_verifier import find_item_coordinates_with_gemini

    try:
        screenshot = capture_screen()
    except Exception as exc:
        logger.error("collect_results: could not capture screen: {}", exc)
        return None

    # Determine left panel bounds — start from y=0 to guarantee item is in crop
    panel_left, panel_top, panel_w, panel_h = 0, 0, 310, 800
    try:
        main_win = app.top_window()
        wr = main_win.rectangle()
        panel_left = max(0, wr.left)
        panel_top = max(0, wr.top)
        panel_w = max(150, min(350, wr.width() // 4))
        panel_h = max(400, wr.height() - 60)  # exclude taskbar / status bar
    except Exception as exc:
        logger.debug("Could not get window rect, using defaults: {}", exc)

    # Crop to left panel so Gemini cannot confuse with center/right content.
    # Skip the top ~80px (title bar + search bar) so Gemini won't mistake the
    # typed search text for the actual tree item.
    SEARCH_BAR_SKIP = 80
    img_h, img_w = screenshot.shape[:2]
    x1 = max(0, panel_left)
    y1 = max(0, panel_top + SEARCH_BAR_SKIP)   # start below the search bar
    x2 = min(img_w, panel_left + panel_w)
    y2 = min(img_h, panel_top + panel_h)
    panel_crop = screenshot[y1:y2, x1:x2] if (x2 > x1 and y2 > y1) else screenshot
    logger.debug("Panel crop (tree only): ({},{}) → ({},{}) = {}x{}px", x1, y1, x2, y2, x2-x1, y2-y1)

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

    crop_h = y2 - y1
    crop_w = x2 - x1

    def _gemini_pick(log_prefix: str) -> tuple[int, int] | None:
        """Ask Gemini and validate coords are inside the panel crop."""
        try:
            coords = find_item_coordinates_with_gemini(
                panel_crop, report_name,
                panel_offset_x=x1, panel_offset_y=y1,
            )
            if not coords:
                return None
            sx, sy = coords
            # Validate: result must land inside the panel (not in center/right)
            if sx < x1 or sx > x2 or sy < y1 or sy > y2:
                logger.warning(
                    "{} Gemini coord ({},{}) outside panel ({},{})→({},{}) — rejected.",
                    log_prefix, sx, sy, x1, y1, x2, y2,
                )
                return None
            return sx, sy
        except Exception as exc:
            logger.warning("{} Gemini error: {}", log_prefix, exc)
            return None

    # Strategy 1: OpenCV — find ALL highlighted regions in the panel
    # Returns (screen_x, screen_y, area) tuples ordered top-to-bottom
    all_regions: list[tuple[int, int, float]] = []
    try:
        all_regions = find_all_highlight_coords(
            screenshot, panel_left, panel_top, panel_w, panel_h
        )
        logger.info("[Agent2] OpenCV found {} highlighted region(s).", len(all_regions))
    except Exception as exc:
        logger.warning("OpenCV detection error: {}", exc)

    if len(all_regions) == 1:
        sx, sy, _ = all_regions[0]
        logger.info("[Agent2] OpenCV single match at ({}, {}).", sx, sy)
        return _make_candidate(sx, sy)

    if len(all_regions) > 1:
        # Multiple highlights: use Gemini with coordinate validation.
        # Gemini finds the exact-name item; we reject any coords outside the panel.
        logger.info(
            "[Agent2] Multiple highlights — using Gemini to pick exact match for '{}'.",
            report_name,
        )
        validated = _gemini_pick("[Multi]")
        if validated:
            sx, sy = validated
            logger.info("[Agent2] Gemini picked ({}, {}) from multiple highlights.", sx, sy)
            return _make_candidate(sx, sy)

        # Gemini failed/invalid — pick the region with the LARGEST highlight area.
        # The fully-highlighted file item covers more pixels than a partially-highlighted
        # folder (e.g. "Summary" folder lit up by a word match is smaller than the
        # full filename highlight on "Job Card Bill Summary New").
        sx, sy, area = max(all_regions, key=lambda r: r[2])
        logger.info(
            "[Agent2] Gemini invalid — using largest-area highlight (area={:.0f}) at ({}, {}).",
            area, sx, sy,
        )
        return _make_candidate(sx, sy)

    # Strategy 2: No OpenCV hits — try Gemini on full panel crop
    validated = _gemini_pick("[Solo]")
    if validated:
        sx, sy = validated
        logger.info("[Agent2] Gemini found item at ({}, {}).", sx, sy)
        return _make_candidate(sx, sy)

    return None


def collect_results_node(state: GlobalState) -> GlobalState:
    """Locate the search result item after typing the report name.

    Excellon's left-panel tree does not expose reliable UIA elements, so
    this node uses screenshot-based detection (OpenCV → Gemini) to find
    the highlighted item and record its screen coordinates for clicking.
    """
    logger.info("[Agent2] Node: collect_results — entering")
    try:
        app = state["app_handle"]
        report_name = state["report_name"]

        # Wait for Excellon to render search results
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
