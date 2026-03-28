"""Node: Click the filter toggle/arrow button to open the filter panel."""

import time
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, capture_region, save_debug_screenshot

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "templates"


def _is_filter_panel_open(main_win) -> bool:
    """Check if the filter panel is currently open."""
    # Check for controls with known filter automation IDs
    filter_ids = {"DateRange", "FromDate", "ToDate", "GenerateReport",
                  "ShowTaxes", "ShowTaxDetails"}
    try:
        for d in main_win.descendants():
            try:
                auto_id = d.element_info.automation_id or ""
                if auto_id in filter_ids:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    # Fallback: check for "Generate Report" button text
    try:
        for btn in main_win.descendants(control_type="Button"):
            try:
                if "generate" in (btn.window_text() or "").lower():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _find_filter_button_opencv(main_win) -> tuple[int, int] | None:
    """Use OpenCV template matching to find the '<' filter button.

    Searches the right edge of the window for a small '<' arrow button.
    Uses a saved template if available, otherwise generates one programmatically.

    Returns:
        (click_x, click_y) screen coordinates, or None if not found.
    """
    import pyautogui

    # Capture the right edge of the screen (where the button lives)
    win_rect = main_win.rectangle()
    # Search the rightmost 100px strip, full height
    region_x = max(win_rect.right - 100, win_rect.left)
    region_y = win_rect.top
    region_w = win_rect.right - region_x
    region_h = win_rect.bottom - win_rect.top

    screen_region = capture_region(region_x, region_y, region_w, region_h)
    gray_region = cv2.cvtColor(screen_region, cv2.COLOR_BGR2GRAY)

    # Try saved template first
    template_path = TEMPLATE_DIR / "filter_arrow_button.png"
    if template_path.exists():
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is not None:
            result = cv2.matchTemplate(gray_region, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > 0.7:
                th, tw = template.shape[:2]
                click_x = region_x + max_loc[0] + tw // 2
                click_y = region_y + max_loc[1] + th // 2
                logger.info("[Agent3] OpenCV template match: confidence={:.2f}", max_val)
                return (click_x, click_y)

    # Generate multiple "<" arrow templates and try each
    # The button could be various sizes, so try a few
    for size in [20, 16, 24, 12, 28]:
        template = _generate_arrow_template(size)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(gray_region, gray_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > 0.6:
            th, tw = gray_template.shape[:2]
            click_x = region_x + max_loc[0] + tw // 2
            click_y = region_y + max_loc[1] + th // 2
            logger.info(
                "[Agent3] OpenCV generated template match: size={}, confidence={:.2f}",
                size, max_val,
            )
            # Save the matched region as template for future use
            try:
                TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
                matched_region = screen_region[
                    max_loc[1]:max_loc[1] + th,
                    max_loc[0]:max_loc[0] + tw,
                ]
                cv2.imwrite(str(template_path), matched_region)
                logger.info("[Agent3] Saved matched region as template for future use.")
            except Exception:
                pass
            return (click_x, click_y)

    # Last resort: look for a small dark arrow shape via edge detection
    edges = cv2.Canny(gray_region, 50, 150)
    # Focus on the bottom half of the right edge
    bottom_half = edges[region_h // 2:, :]
    contours, _ = cv2.findContours(bottom_half, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Filter for small, roughly square shapes (button-sized)
        if 8 < w < 40 and 8 < h < 40 and 0.5 < w / h < 2.0:
            click_x = region_x + x + w // 2
            click_y = region_y + (region_h // 2) + y + h // 2
            logger.info(
                "[Agent3] OpenCV contour match: rect=({},{},{}x{}) at ({},{})",
                x, y, w, h, click_x, click_y,
            )
            return (click_x, click_y)

    logger.warning("[Agent3] OpenCV could not find the '<' button.")
    return None


def _generate_arrow_template(size: int = 20) -> np.ndarray:
    """Generate a synthetic '<' arrow button template.

    Args:
        size: Size of the template in pixels.

    Returns:
        BGR numpy array of the template.
    """
    img = np.ones((size, size, 3), dtype=np.uint8) * 230  # Light gray background
    # Draw a "<" arrow
    center_x = size // 2
    center_y = size // 2
    arrow_size = size // 3
    pts = np.array([
        [center_x + arrow_size, center_y - arrow_size],
        [center_x - arrow_size, center_y],
        [center_x + arrow_size, center_y + arrow_size],
    ], np.int32)
    cv2.polylines(img, [pts], False, (80, 80, 80), 2)
    return img


def click_arrow_button_node(state: GlobalState) -> GlobalState:
    """Find and click the filter expand/toggle button.

    Searches for arrow/expand button at the bottom-right of the
    report content area, then verifies the filter panel opened.
    """
    logger.info("[Agent3] Node: click_arrow_button — entering")
    try:
        app = state["app_handle"]
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        # Check if filter panel is ALREADY open (e.g. report opened with filters visible)
        if _is_filter_panel_open(main_win):
            state["filter_window_open"] = True
            logger.info("[Agent3] Filter panel already open, skipping toggle click.")
            return state

        # Strategy 1: Find "Report Filters" label, then find the "<" button
        # immediately to its left.
        # Layout at bottom-right: ... [>] [<] [Report Filters]
        # We want the "<" button, NOT the ">" scrollbar button.
        import pyautogui
        filter_btn = None
        all_controls = main_win.descendants()
        report_filters_label = None

        for ctrl in all_controls:
            try:
                text = ctrl.window_text().strip()
                if text.lower() in ("report filters", "reportfilters"):
                    report_filters_label = ctrl
                    break
            except Exception:
                continue

        if report_filters_label is not None:
            label_rect = report_filters_label.rectangle()
            logger.info(
                "[Agent3] Found 'Report Filters' label at ({},{}) to ({},{}).",
                label_rect.left, label_rect.top, label_rect.right, label_rect.bottom,
            )
            # Collect ALL buttons and log them for debugging
            buttons = [c for c in all_controls
                       if getattr(c.element_info, 'control_type', '') in
                       ('Button', 'ToggleButton')]

            # Find buttons with text "<" — pick the one closest to the label's left edge
            lt_buttons = []
            for btn in buttons:
                try:
                    text = btn.window_text().strip()
                    if text == "<":
                        br = btn.rectangle()
                        # Distance from this button's right edge to the label's left edge
                        dist = abs(br.right - label_rect.left)
                        lt_buttons.append((btn, br, dist))
                        logger.debug(
                            "[Agent3] Found '<' button at ({},{}) to ({},{}), "
                            "dist to label={}",
                            br.left, br.top, br.right, br.bottom, dist,
                        )
                except Exception:
                    continue

            if lt_buttons:
                # Pick the "<" button closest to the Report Filters label
                lt_buttons.sort(key=lambda x: x[2])
                filter_btn = lt_buttons[0][0]
                btn_rect = lt_buttons[0][1]
                logger.info(
                    "[Agent3] Selected '<' button at ({},{}) to ({},{}) — "
                    "closest to Report Filters label (dist={}).",
                    btn_rect.left, btn_rect.top, btn_rect.right, btn_rect.bottom,
                    lt_buttons[0][2],
                )

        # Strategy 2: If no "<" button found near label, use pyautogui to
        # click just to the left of the Report Filters label
        if filter_btn is None and report_filters_label is not None:
            label_rect = report_filters_label.rectangle()
            # Click at the bottom of the label area — the "<" button
            # is at the bottom of the "Report Filters" strip
            click_x = (label_rect.left + label_rect.right) // 2
            click_y = label_rect.bottom - 15
            logger.info(
                "[Agent3] No '<' button found, clicking left of label at ({},{}).",
                click_x, click_y,
            )
            pyautogui.click(click_x, click_y)
            time.sleep(1.0)
            # Check if it opened
            for combo in main_win.descendants(control_type="ComboBox"):
                try:
                    cn = (combo.element_info.name or "").lower()
                    ct = combo.window_text().lower()
                    if "date" in cn or "range" in cn or "date" in ct:
                        state["filter_window_open"] = True
                        logger.info("[Agent3] Filter panel opened via position click.")
                        return state
                except Exception:
                    continue

        # Strategy 3: Button/control with filter-related automation ID
        if filter_btn is None:
            for ctrl in all_controls:
                try:
                    auto_id = (ctrl.element_info.automation_id or "").lower()
                    name = (ctrl.element_info.name or "").lower()
                    if ("reportfilter" in auto_id or "filterbutton" in auto_id
                            or "filtertoggle" in auto_id
                            or "report filter" in name):
                        filter_btn = ctrl
                        logger.info("[Agent3] Found filter control by ID: '{}'", auto_id)
                        break
                except Exception:
                    continue

        if filter_btn is None:
            # Strategy 4: OpenCV — find the "<" button via template matching
            logger.info("[Agent3] Trying OpenCV fallback to find '<' button.")
            try:
                opencv_result = _find_filter_button_opencv(main_win)
                if opencv_result is not None:
                    click_x, click_y = opencv_result
                    logger.info("[Agent3] OpenCV found '<' button at ({},{}).", click_x, click_y)
                    pyautogui.click(click_x, click_y)
                    time.sleep(1.0)
                    if _is_filter_panel_open(main_win):
                        state["filter_window_open"] = True
                        logger.info("[Agent3] Filter panel opened via OpenCV click.")
                        return state
            except Exception as exc:
                logger.debug("[Agent3] OpenCV fallback failed: {}", exc)

        if filter_btn is None:
            state["error"] = (
                "Filter toggle button not found. Could not find "
                "'Report Filters' label, '<' button, or OpenCV match."
            )
            logger.error("[Agent3] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "click_arrow_not_found")
            except Exception:
                pass
            return state

        filter_btn.click_input()
        logger.info("Filter toggle button clicked: '{}'", filter_btn.window_text())

        # Verify filter panel opened
        timeout = 10
        start = time.time()
        while time.time() - start < timeout:
            if _is_filter_panel_open(main_win):
                state["filter_window_open"] = True
                logger.info("[Agent3] Filter panel confirmed open.")
                # Wait for filter panel controls to fully render
                time.sleep(2.0)
                return state
            time.sleep(0.5)

        # If first click didn't work, try OpenCV as final fallback
        logger.info("[Agent3] First click didn't open filter, trying OpenCV fallback.")
        try:
            opencv_result = _find_filter_button_opencv(main_win)
            if opencv_result is not None:
                click_x, click_y = opencv_result
                logger.info("[Agent3] OpenCV found '<' button at ({},{}).", click_x, click_y)
                pyautogui.click(click_x, click_y)
                time.sleep(1.0)
                if _is_filter_panel_open(main_win):
                    state["filter_window_open"] = True
                    logger.info("[Agent3] Filter panel opened via OpenCV fallback.")
                    return state
        except Exception as exc:
            logger.debug("[Agent3] OpenCV fallback failed: {}", exc)

        state["error"] = (
            "Filter panel did not appear after clicking toggle and OpenCV fallback."
        )
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_arrow_timeout")
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
