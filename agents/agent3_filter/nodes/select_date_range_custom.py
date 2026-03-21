"""Node: Select 'Custom' from the Date Range dropdown."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def select_date_range_custom_node(state: GlobalState) -> GlobalState:
    """Open the Date Range dropdown and select 'Custom'.

    This enables manual entry of From and To dates.
    """
    logger.info("[Agent3] Node: select_date_range_custom — entering")
    try:
        app = state["app_handle"]
        main_win = app.top_window()

        # Find the Date Range dropdown
        date_combo = None
        combos = main_win.descendants(control_type="ComboBox")
        for combo in combos:
            try:
                name = (combo.element_info.name or "").lower()
                text = combo.window_text().lower()
                auto_id = (combo.element_info.automation_id or "").lower()
                if "date" in name or "range" in name or "date" in auto_id:
                    date_combo = combo
                    break
            except Exception:
                continue

        if date_combo is None:
            state["error"] = "Date Range dropdown not found in filter panel."
            logger.error("[Agent3] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "date_range_not_found")
            except Exception:
                pass
            return state

        # Click to open dropdown
        date_combo.click_input()
        time.sleep(0.3)
        logger.debug("Date Range dropdown clicked.")

        # Find and click 'Custom' option
        custom_found = False

        # Strategy 1: Look for ListItem children
        try:
            list_items = date_combo.descendants(control_type="ListItem")
            for item in list_items:
                try:
                    text = item.window_text().strip().lower()
                    if "custom" in text:
                        item.click_input()
                        custom_found = True
                        logger.info("Selected 'Custom' from dropdown (ListItem).")
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Strategy 2: Look in expanded list popup
        if not custom_found:
            try:
                from pywinauto import Desktop
                all_windows = Desktop(backend="uia").windows()
                for win in all_windows:
                    try:
                        items = win.descendants(control_type="ListItem")
                        for item in items:
                            try:
                                text = item.window_text().strip().lower()
                                if "custom" in text:
                                    item.click_input()
                                    custom_found = True
                                    logger.info("Selected 'Custom' from popup list.")
                                    break
                            except Exception:
                                continue
                        if custom_found:
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        # Strategy 3: Type 'Custom' into the combo
        if not custom_found:
            try:
                date_combo.type_keys("Custom{ENTER}")
                custom_found = True
                logger.info("Typed 'Custom' into Date Range combo.")
            except Exception:
                pass

        if not custom_found:
            state["error"] = "Could not select 'Custom' from Date Range dropdown."
            logger.error("[Agent3] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "custom_not_found")
            except Exception:
                pass
            return state

        time.sleep(0.3)

        # Verify Custom is selected
        try:
            current = date_combo.window_text().strip().lower()
            if "custom" in current:
                logger.info("Verified: 'Custom' is now selected.")
            else:
                logger.warning("Date Range value: '{}' — may not be Custom.", current)
        except Exception:
            pass

        state["date_range_set"] = True
        logger.info("[Agent3] Node: select_date_range_custom — completed")

    except Exception as exc:
        state["error"] = f"select_date_range_custom failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "select_date_range_error")
        except Exception:
            pass

    return state
