"""Node: Enter the From Date into the filter."""

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.uia_retry import find_descendant_by_auto_id, find_descendant_by_text


def _normalize_date(date_str: str) -> str:
    """Convert date from DD/MM/YYYY to DD-MM-YYYY format."""
    return date_str.replace("/", "-")


def _find_date_field(main_win, auto_id: str, label: str):
    """Find a date field via UIA with retries — by automation_id or text."""
    field = find_descendant_by_auto_id(main_win, auto_id, retries=3, delay=2.0)
    if field is not None:
        return field
    return find_descendant_by_text(main_win, label, retries=3, delay=2.0)


def _enter_date(main_win, auto_id: str, label: str, date_value: str) -> bool:
    """Find a date field and type the date."""
    date_normalized = _normalize_date(date_value)

    field = _find_date_field(main_win, auto_id, label)
    if field is not None:
        r = field.rectangle()
        click_x = r.left + 40
        click_y = (r.top + r.bottom) // 2
        logger.info("[FILTER] Clicking '{}' at ({},{}).", label, click_x, click_y)
        pyautogui.click(click_x, click_y)
        time.sleep(0.5)
    else:
        logger.warning("[FILTER] '{}' not found, assuming focus from TAB.", label)

    # Select all, clear, type date
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.3)
    pyautogui.press("backspace")
    time.sleep(0.3)
    logger.info("[FILTER] Typing '{}' in '{}'.", date_normalized, label)
    pyautogui.typewrite(date_normalized, interval=0.05)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.5)
    return True


def enter_from_date_node(state: GlobalState) -> GlobalState:
    """Type the From Date value into the FromDate field."""
    logger.info("[Agent3] Node: enter_from_date — entering")
    try:
        app = state["app_handle"]
        from_date = state.get("from_date") or settings.filter_from_date
        state["from_date"] = from_date
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        _enter_date(main_win, "FromDate", "From Date", from_date)
        logger.info("[Agent3] From date entered: {}", from_date)

    except Exception as exc:
        state["error"] = f"enter_from_date failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "enter_from_date_error")
        except Exception:
            pass

    return state
