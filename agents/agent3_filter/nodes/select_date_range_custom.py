"""Node: Select 'Custom' from the Date Range dropdown."""

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.uia_retry import find_all_by_text_in_panel


def select_date_range_custom_node(state: GlobalState) -> GlobalState:
    """Open the Date Range dropdown and select 'Custom'."""
    logger.info("[Agent3] Node: select_date_range_custom — entering")
    try:
        app = state["app_handle"]
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        time.sleep(2.0)

        # 1. Find Date Range control with retried search
        # Search for multiple known texts — use whichever is found
        search_texts = ["Date Range", "Month To Date", "Week To Date",
                        "Year To Date", "Custom", "Previous Month"]
        found = find_all_by_text_in_panel(main_win, search_texts, retries=5, delay=2.0)

        if not found:
            state["error"] = "Date Range control not found after retries."
            logger.error("[Agent3] {}", state["error"])
            return state

        logger.info("[Agent3] Found filter panel controls: {}", list(found.keys()))

        # Determine which control to click for the dropdown
        date_ctrl = found.get("Date Range")
        if date_ctrl is not None:
            dr = date_ctrl.rectangle()
            click_x = dr.right - 15
            click_y = (dr.top + dr.bottom) // 2
            logger.info("[Agent3] Clicking Date Range dropdown at ({},{}).", click_x, click_y)
        else:
            # Use any found date range value as the dropdown itself
            for key in ["Month To Date", "Week To Date", "Year To Date",
                        "Previous Month", "Custom"]:
                if key in found:
                    ctrl = found[key]
                    r = ctrl.rectangle()
                    click_x = r.right - 15
                    click_y = (r.top + r.bottom) // 2
                    logger.info("[Agent3] Clicking '{}' dropdown at ({},{}).", key, click_x, click_y)
                    break

        # 2. Click the dropdown to open it
        pyautogui.click(click_x, click_y)
        time.sleep(1.0)

        # 3. Select 'Custom' — it's the last item in the dropdown.
        # Use keyboard: End key jumps to last item, Enter selects it.
        pyautogui.press("end")
        time.sleep(0.3)
        pyautogui.press("enter")
        logger.info("[Agent3] Selected 'Custom' via keyboard (End + Enter).")

        time.sleep(1.0)

        # 4. Press TAB to unlock From/To date fields
        logger.info("[Agent3] Pressing TAB to unlock date fields.")
        pyautogui.press("tab")
        time.sleep(0.5)

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
