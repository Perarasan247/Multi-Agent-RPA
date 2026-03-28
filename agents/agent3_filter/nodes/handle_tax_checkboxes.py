"""Node: Handle tax-related checkboxes based on report config."""

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.uia_retry import find_descendant_by_text


def _tick_checkbox(window, label: str) -> bool:
    """Find and tick a checkbox by its label text.

    Uses retried UIA descendants() search. Works with both CheckBox
    and DataItem control types across different reports.
    Handles minor text variations like "Show Tax Detail" vs "Show Tax Details".
    """
    # Try exact match first, then with/without trailing 's'
    candidates = [label]
    if label.endswith("s"):
        candidates.append(label[:-1])  # "Show Tax Details" -> "Show Tax Detail"
    else:
        candidates.append(label + "s")  # "Show Tax Detail" -> "Show Tax Details"

    target = None
    for candidate in candidates:
        target = find_descendant_by_text(window, candidate, retries=5, delay=2.0)
        if target is not None:
            logger.info("[FILTER] Matched '{}' for label '{}'.", candidate, label)
            break

    if not target:
        logger.error("[FILTER] Could not find: '{}'", label)
        return False

    # Read state if possible to avoid unchecking
    try:
        if hasattr(target, 'get_toggle_state') and target.get_toggle_state() == 1:
            logger.info("[FILTER] '{}' is already checked.", label)
            return True
    except Exception:
        pass

    logger.info("[FILTER] Clicking checkbox: '{}'", label)
    r = target.rectangle()
    # Click slightly inside the label area to hit the box itself
    pyautogui.click(r.left + 10, r.top + (r.height() // 2))
    time.sleep(0.5)
    return True


def handle_tax_checkboxes_node(state: GlobalState) -> GlobalState:
    """Apply tax filter checkboxes as specified in report config."""
    logger.info("[Agent3] Node: handle_tax_checkboxes — entering")
    try:
        filters = state.get("filters", [])

        if not filters:
            logger.info("[Agent3] No filters configured, skipping checkboxes.")
            state["tax_boxes_handled"] = True
            return state

        app = state["app_handle"]
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        # Wait for filter panel to fully render
        time.sleep(5.0)

        for label in filters:
            if not _tick_checkbox(main_win, label):
                logger.warning("[Agent3] Failed to tick '{}'", label)

        state["tax_boxes_handled"] = True
        logger.info("[Agent3] Tax checkboxes handled for filters: {}", filters)

    except Exception as exc:
        state["error"] = f"handle_tax_checkboxes failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "handle_tax_checkboxes_error")
        except Exception:
            pass

    return state
