"""Node: Click the filter toggle/arrow button to open the filter panel.

4-tier fallback:
  Tier 1  UIA     — walk element tree; find < button closest to Filters label
  Tier 2  OpenCV  — template match; real saved template first, then synthetic
  Tier 3  Gemini  — vision API locates the < button from screenshot
  Tier 4  Claude  — vision fallback, fires ONLY when Gemini fails/unavailable

After every click attempt:
  • Check if the About dialog opened (wrong button hit) — close it via X button
  • Check if the filter panel opened successfully

If the filter panel is already open when the node starts, skip everything.

Label variants handled (case-insensitive):
  "Report Filters", "Report Filter", "Filters", "Filter"
"""

import base64
import io
import re
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.window_manager import get_main_window

TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "assets" / "templates"
)

_FILTER_LABEL_VARIANTS = (
    "report filters",
    "reportfilters",
    "report filter",
    "reportfilter",
    "filters",
    "filter",
)


# ── Filter-panel open detection ──────────────────────────────────────────────


def _is_filter_panel_open(main_win) -> bool:
    """Return True if the filter panel is already visible."""
    filter_auto_ids = {
        "DateRange", "FromDate", "ToDate", "GenerateReport",
        "ShowTaxes", "ShowTaxDetails",
    }
    try:
        for d in main_win.descendants():
            try:
                if (d.element_info.automation_id or "") in filter_auto_ids:
                    return True
            except Exception:
                continue
    except Exception:
        pass

    try:
        for btn in main_win.descendants(control_type="Button"):
            try:
                if "generate" in (btn.window_text() or "").lower():
                    return True
            except Exception:
                continue
    except Exception:
        pass

    # ComboBox visible in the right-side panel (date range picker etc.)
    try:
        wr = main_win.rectangle()
        panel_x = wr.right - 450
        for combo in main_win.descendants(control_type="ComboBox"):
            try:
                if combo.rectangle().left > panel_x:
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


# ── About dialog recovery ────────────────────────────────────────────────────


def _close_about_dialog(app) -> bool:
    """Detect and close the About dialog by clicking its X button with the mouse.

    Returns True if the dialog was found and closed.
    """
    try:
        for win in app.windows():
            if (win.window_text() or "").strip().lower() != "about":
                continue

            logger.warning("[ClickArrow] About dialog detected — closing via X button.")
            wr = win.rectangle()

            # Tier A: find Close button via UIA
            closed = False
            try:
                for btn in win.descendants(control_type="Button"):
                    btn_name = (btn.element_info.name or "").lower()
                    if btn_name in ("close", "x"):
                        br = btn.rectangle()
                        pyautogui.click((br.left + br.right) // 2, (br.top + br.bottom) // 2)
                        time.sleep(0.5)
                        closed = True
                        break
            except Exception:
                pass

            if not closed:
                # Tier B: title-bar X is always near top-right of the dialog window
                pyautogui.click(wr.right - 13, wr.top + 13)
                time.sleep(0.5)

            logger.info("[ClickArrow] About dialog closed.")
            return True
    except Exception as exc:
        logger.debug("[ClickArrow] About dialog check error: {}", exc)
    return False


# ── Tier 1: UIA ──────────────────────────────────────────────────────────────


def _find_via_uia(main_win) -> Optional[Tuple[int, int]]:
    try:
        controls = list(main_win.descendants())
    except Exception:
        return None

    # Find the Filters label (any variant)
    label_rect = None
    for ctrl in controls:
        try:
            txt = (ctrl.window_text() or "").strip().lower().replace(":", "").replace(" ", "")
            for variant in _FILTER_LABEL_VARIANTS:
                if txt == variant.replace(" ", ""):
                    label_rect = ctrl.rectangle()
                    logger.info(
                        "[ClickArrow/UIA] Found label '{}' at ({},{}).",
                        ctrl.window_text().strip(),
                        label_rect.left, label_rect.top,
                    )
                    break
        except Exception:
            continue
        if label_rect:
            break

    # Automation-ID fallback when label not found
    if label_rect is None:
        for ctrl in controls:
            try:
                auto_id = (ctrl.element_info.automation_id or "").lower()
                name = (ctrl.element_info.name or "").lower()
                if any(k in auto_id for k in ("reportfilter", "filterbutton", "filtertoggle")) \
                        or "report filter" in name:
                    r = ctrl.rectangle()
                    logger.info("[ClickArrow/UIA] Found control by auto-id '{}'.", auto_id)
                    return (r.left + r.right) // 2, (r.top + r.bottom) // 2
            except Exception:
                continue
        return None

    # Among all < buttons, pick the one whose right edge is closest to the label
    lt_buttons = []
    for ctrl in controls:
        try:
            ct = getattr(ctrl.element_info, "control_type", "")
            if ct not in ("Button", "ToggleButton"):
                continue
            if (ctrl.window_text() or "").strip() == "<":
                br = ctrl.rectangle()
                dist = abs(br.right - label_rect.left)
                lt_buttons.append((dist, br))
        except Exception:
            continue

    if lt_buttons:
        lt_buttons.sort(key=lambda x: x[0])
        br = lt_buttons[0][1]
        cx, cy = (br.left + br.right) // 2, (br.top + br.bottom) // 2
        logger.info("[ClickArrow/UIA] < button at ({},{}).", cx, cy)
        return cx, cy

    # No < button found — the "Report Filters" label is a vertical strip on the
    # right edge. The < button sits at the BOTTOM of that strip, not the center.
    cx = (label_rect.left + label_rect.right) // 2
    cy = label_rect.bottom - 20
    logger.info("[ClickArrow/UIA] No < button, clicking bottom of label strip at ({},{}).", cx, cy)
    return cx, cy


# ── Tier 2: OpenCV ───────────────────────────────────────────────────────────


def _generate_arrow_template(size: int) -> np.ndarray:
    img = np.ones((size, size, 3), dtype=np.uint8) * 230
    c, a = size // 2, size // 3
    pts = np.array([[c + a, c - a], [c - a, c], [c + a, c + a]], np.int32)
    cv2.polylines(img, [pts], False, (80, 80, 80), 2)
    return img


def _find_via_opencv(main_win, screen: np.ndarray) -> Optional[Tuple[int, int]]:
    try:
        wr = main_win.rectangle()
        rx = max(wr.left, wr.right - 120)
        ry, rw, rh = wr.top, wr.right - rx, wr.bottom - wr.top

        crop = screen[ry:ry + rh, rx:rx + rw]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        template_path = TEMPLATE_DIR / "filter_arrow_button.png"

        # Real saved template
        if template_path.exists():
            tmpl = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if tmpl is not None:
                res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
                _, val, _, loc = cv2.minMaxLoc(res)
                if val > 0.70:
                    th, tw = tmpl.shape[:2]
                    cx = rx + loc[0] + tw // 2
                    cy = ry + loc[1] + th // 2
                    logger.info("[ClickArrow/OpenCV] Saved template: conf={:.2f}", val)
                    return cx, cy

        # Synthetic templates at multiple sizes
        for size in [20, 16, 24, 12, 28]:
            tmpl = cv2.cvtColor(_generate_arrow_template(size), cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
            _, val, _, loc = cv2.minMaxLoc(res)
            if val > 0.60:
                th, tw = tmpl.shape[:2]
                cx = rx + loc[0] + tw // 2
                cy = ry + loc[1] + th // 2
                logger.info("[ClickArrow/OpenCV] Synthetic size={}: conf={:.2f}", size, val)
                try:
                    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(template_path), crop[loc[1]:loc[1]+th, loc[0]:loc[0]+tw])
                except Exception:
                    pass
                return cx, cy

        # Canny edge contours — last resort
        edges = cv2.Canny(gray, 50, 150)
        bottom = edges[rh // 2:, :]
        contours, _ = cv2.findContours(bottom, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 8 < w < 40 and 8 < h < 40 and 0.5 < w / h < 2.0:
                cx = rx + x + w // 2
                cy = ry + (rh // 2) + y + h // 2
                logger.info("[ClickArrow/OpenCV] Contour at ({},{}).", cx, cy)
                return cx, cy
    except Exception as exc:
        logger.debug("[ClickArrow/OpenCV] failed: {}", exc)
    return None


# ── Tier 3: Gemini ───────────────────────────────────────────────────────────

_VISION_PROMPT = (
    "This is the bottom-right corner of an Excellon ERP report window. "
    "On the right edge there is a vertical label that says 'Report Filters' or 'Filters'. "
    "At the BOTTOM of that vertical label strip there is a small left-pointing arrow or "
    "chevron button ( < ) that opens the report filter panel. "
    "There may also be a right-pointing arrow ( > ) nearby — do NOT select that one. "
    "Find ONLY the left-pointing < button at the bottom of the Filters strip. "
    "Reply with ONLY two integers separated by a space: x y "
    "(pixel coordinates of the center of that button within this image). "
    "Example reply: 320 278"
)


def _crop_bottom_right(main_win, screen: np.ndarray) -> Tuple[np.ndarray, int, int]:
    """Return (cropped_image, offset_x, offset_y) for the bottom-right corner.

    Uses a wider crop (350x300) so the vertical 'Report Filters' strip and the
    < button at its bottom are fully visible in the image sent to vision APIs.
    """
    wr = main_win.rectangle()
    rx = max(wr.left, wr.right - 350)
    ry = max(wr.top, wr.bottom - 300)
    rw = wr.right - rx
    rh = wr.bottom - ry
    return screen[ry:ry + rh, rx:rx + rw], rx, ry


def _parse_coords(text: str, rw: int, rh: int) -> Optional[Tuple[int, int]]:
    match = re.search(r"(\d+)\s+(\d+)", text)
    if not match:
        return None
    x, y = int(match.group(1)), int(match.group(2))
    if 0 <= x <= rw and 0 <= y <= rh:
        return x, y
    return None


def _find_via_gemini(main_win, screen: np.ndarray) -> Optional[Tuple[int, int]]:
    try:
        import google.generativeai as genai
        from PIL import Image
        from config.settings import settings

        if not settings.gemini_api_key:
            logger.debug("[ClickArrow/Gemini] No API key.")
            return None

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        crop, rx, ry = _crop_bottom_right(main_win, screen)
        rh, rw = crop.shape[:2]
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        response = model.generate_content([pil_img, _VISION_PROMPT])
        rel = _parse_coords((response.text or "").strip(), rw, rh)
        if rel:
            cx, cy = rx + rel[0], ry + rel[1]
            logger.info("[ClickArrow/Gemini] < button at ({},{}).", cx, cy)
            return cx, cy
        logger.warning("[ClickArrow/Gemini] Could not parse coords from: {}", response.text)
    except Exception as exc:
        logger.debug("[ClickArrow/Gemini] failed: {}", exc)
    return None


# ── Tier 4: Claude ───────────────────────────────────────────────────────────


def _find_via_claude(main_win, screen: np.ndarray) -> Optional[Tuple[int, int]]:
    try:
        import anthropic
        from PIL import Image
        from config.settings import settings

        if not settings.anthropic_api_key:
            logger.debug("[ClickArrow/Claude] No API key.")
            return None

        crop, rx, ry = _crop_bottom_right(main_win, screen)
        rh, rw = crop.shape[:2]
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }],
        )
        text = (response.content[0].text or "").strip()
        rel = _parse_coords(text, rw, rh)
        if rel:
            cx, cy = rx + rel[0], ry + rel[1]
            logger.info("[ClickArrow/Claude] < button at ({},{}).", cx, cy)
            return cx, cy
        logger.warning("[ClickArrow/Claude] Could not parse coords from: {}", text)
    except Exception as exc:
        logger.debug("[ClickArrow/Claude] failed: {}", exc)
    return None


# ── Main node ────────────────────────────────────────────────────────────────


def click_arrow_button_node(state: GlobalState) -> GlobalState:
    """Click the < filter toggle button with 4-tier fallback and About dialog recovery."""
    logger.info("[Agent3] Node: click_arrow_button — entering")
    try:
        app = state["app_handle"]
        main_win = get_main_window(app)

        if _is_filter_panel_open(main_win):
            state["filter_window_open"] = True
            logger.info("[Agent3] Filter panel already open — skipping.")
            return state

        screen = capture_screen()
        gemini_failed = False

        tiers = [
            ("UIA",    lambda: _find_via_uia(main_win)),
            ("OpenCV", lambda: _find_via_opencv(main_win, screen)),
            ("Gemini", lambda: _find_via_gemini(main_win, screen)),
            ("Claude", lambda: _find_via_claude(main_win, screen)),
        ]

        for tier_name, locator in tiers:
            # Claude only runs if Gemini failed
            if tier_name == "Claude" and not gemini_failed:
                logger.info("[Agent3] ClickArrow — Gemini succeeded, skipping Claude.")
                continue

            try:
                coords = locator()
            except Exception as exc:
                logger.warning("[Agent3] ClickArrow tier '{}' raised: {}", tier_name, exc)
                coords = None

            if coords is None:
                logger.info("[Agent3] ClickArrow tier '{}' — button not found.", tier_name)
                if tier_name == "Gemini":
                    gemini_failed = True
                continue

            cx, cy = coords
            logger.info("[Agent3] ClickArrow tier '{}' — clicking ({},{}).", tier_name, cx, cy)
            pyautogui.click(cx, cy)
            time.sleep(0.6)

            # Check for About dialog (wrong button hit) — close and try next tier
            if _close_about_dialog(app):
                logger.warning(
                    "[Agent3] Tier '{}' opened About dialog — closed it, trying next tier.",
                    tier_name,
                )
                if tier_name == "Gemini":
                    gemini_failed = True
                screen = capture_screen()
                continue

            # Check if filter panel opened
            time.sleep(0.5)
            if _is_filter_panel_open(main_win):
                state["filter_window_open"] = True
                # Save the real button image as OpenCV template for future runs
                _try_save_template(screen, main_win, cx, cy)
                time.sleep(1.5)
                logger.info(
                    "[Agent3] Node: click_arrow_button — opened via tier '{}'.", tier_name,
                )
                return state

            logger.warning(
                "[Agent3] Tier '{}' clicked ({},{}) but filter panel did not open.",
                tier_name, cx, cy,
            )
            if tier_name == "Gemini":
                gemini_failed = True
            screen = capture_screen()

        state["error"] = (
            "click_arrow_button: all 4 tiers failed to open the filter panel "
            "(UIA, OpenCV, Gemini, Claude). Check screenshots for details."
        )
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_arrow_all_tiers_failed")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"click_arrow_button failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_arrow_error")
        except Exception:
            pass

    return state


def _try_save_template(screen: np.ndarray, main_win, cx: int, cy: int) -> None:
    """Save a 30x30 crop around the clicked button as the OpenCV template."""
    try:
        template_path = TEMPLATE_DIR / "filter_arrow_button.png"
        if template_path.exists():
            return
        TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        pad = 15
        crop = screen[cy - pad:cy + pad, cx - pad:cx + pad]
        if crop.size > 0:
            cv2.imwrite(str(template_path), crop)
            logger.info("[ClickArrow] Saved real button template for future OpenCV runs.")
    except Exception:
        pass
