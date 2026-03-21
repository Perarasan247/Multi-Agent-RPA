"""Node: Enter the To Date into the filter."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.keyboard_mouse import clear_field, type_text_slow, press_key
from automation.screenshot import capture_screen, save_debug_screenshot


def enter_to_date_node(state: GlobalState) -> GlobalState:
    """Type the To Date value into the date field.

    Either tabs to the field or finds it by label.
    Format: DD/MM/YYYY.
    """
    logger.info("[Agent3] Node: enter_to_date — entering")
    try:
        app = state["app_handle"]
        to_date = state.get("to_date") or settings.filter_to_date
        state["to_date"] = to_date

        main_win = app.top_window()

        # Try to find the To Date field explicitly
        to_field = None
        edits = main_win.descendants(control_type="Edit")
        for edit in edits:
            try:
                name = (edit.element_info.name or "").lower()
                auto_id = (edit.element_info.automation_id or "").lower()
                if "to" in name or "to" in auto_id or "end" in name:
                    to_field = edit
                    break
            except Exception:
                continue

        if to_field is not None:
            clear_field(to_field)
            type_text_slow(to_field, to_date, delay=0.05)
        else:
            # Fallback: Tab from From Date field, then type
            press_key("tab")
            time.sleep(0.3)
            import pyautogui
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("delete")
            time.sleep(0.1)
            for char in to_date:
                pyautogui.typewrite(char, interval=0.05)

        logger.info("[Agent3] To date entered: {}", to_date)

    except Exception as exc:
        state["error"] = f"enter_to_date failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "enter_to_date_error")
        except Exception:
            pass

    return state
