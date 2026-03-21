"""Node: Handle tax-related checkboxes based on report config."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def _find_and_check_checkbox(main_win, label: str) -> bool:
    """Find a checkbox by label and ensure it is checked.

    Args:
        main_win: The main application window.
        label: Text label to search for (case-insensitive).

    Returns:
        True if the checkbox was found and is now checked.
    """
    checkboxes = main_win.descendants(control_type="CheckBox")
    for cb in checkboxes:
        try:
            text = cb.window_text().strip().lower()
            name = (cb.element_info.name or "").lower()
            if label.lower() in text or label.lower() in name:
                # Check current toggle state
                try:
                    toggle_state = cb.get_toggle_state()
                    # 0 = unchecked, 1 = checked, 2 = indeterminate
                    if toggle_state == 1:
                        logger.info("Checkbox '{}' already checked.", label)
                        return True
                except Exception:
                    pass

                # Try legacy state check
                try:
                    legacy = cb.legacy_properties()
                    state_val = legacy.get("State", 0)
                    # STATE_SYSTEM_CHECKED = 0x10
                    if state_val & 0x10:
                        logger.info("Checkbox '{}' already checked (legacy).", label)
                        return True
                except Exception:
                    pass

                # Click to check it
                cb.click_input()
                time.sleep(0.3)
                logger.info("Checkbox '{}' clicked to check.", label)
                return True
        except Exception:
            continue

    logger.warning("Checkbox '{}' not found.", label)
    return False


def handle_tax_checkboxes_node(state: GlobalState) -> GlobalState:
    """Apply tax filter checkboxes as specified in report config.

    If no filters are configured, this node passes cleanly.
    """
    logger.info("[Agent3] Node: handle_tax_checkboxes — entering")
    try:
        filters = state.get("filters", [])

        if not filters:
            logger.info("[Agent3] No filters configured, skipping checkboxes.")
            state["tax_boxes_handled"] = True
            return state

        app = state["app_handle"]
        main_win = app.top_window()

        if "Show Taxes" in filters:
            found = _find_and_check_checkbox(main_win, "Show Tax")
            if not found:
                logger.warning("Could not find 'Show Taxes' checkbox.")

        if "Show Tax Detail" in filters:
            found = _find_and_check_checkbox(main_win, "Show Tax Detail")
            if not found:
                logger.warning("Could not find 'Show Tax Detail' checkbox.")

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
