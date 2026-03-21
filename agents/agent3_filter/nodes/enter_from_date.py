"""Node: Enter the From Date into the filter."""

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.keyboard_mouse import clear_field, type_text_slow
from automation.screenshot import capture_screen, save_debug_screenshot


def enter_from_date_node(state: GlobalState) -> GlobalState:
    """Type the From Date value into the active/found date field.

    Uses the date from settings or state override.
    Format: DD/MM/YYYY.
    """
    logger.info("[Agent3] Node: enter_from_date — entering")
    try:
        app = state["app_handle"]
        from_date = state.get("from_date") or settings.filter_from_date
        state["from_date"] = from_date

        main_win = app.top_window()

        # Try to find the From Date field explicitly
        from_field = None
        edits = main_win.descendants(control_type="Edit")
        for edit in edits:
            try:
                name = (edit.element_info.name or "").lower()
                auto_id = (edit.element_info.automation_id or "").lower()
                if "from" in name or "from" in auto_id or "start" in name:
                    from_field = edit
                    break
            except Exception:
                continue

        if from_field is not None:
            clear_field(from_field)
            type_text_slow(from_field, from_date, delay=0.05)
        else:
            # Fallback: assume focus is already on From Date from Tab
            import pyautogui
            pyautogui.hotkey("ctrl", "a")
            import time
            time.sleep(0.1)
            pyautogui.press("delete")
            time.sleep(0.1)
            for char in from_date:
                pyautogui.typewrite(char, interval=0.05)

        logger.info("[Agent3] From date entered: {}", from_date)

    except Exception as exc:
        state["error"] = f"enter_from_date failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "enter_from_date_error")
        except Exception:
            pass

    return state
