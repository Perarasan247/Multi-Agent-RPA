"""Node: Enter the To Date into the filter."""

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.screenshot import capture_screen, save_debug_screenshot
from agents.agent3_filter.nodes.enter_from_date import _enter_date, _normalize_date


def enter_to_date_node(state: GlobalState) -> GlobalState:
    """Type the To Date value into the ToDate field."""
    logger.info("[Agent3] Node: enter_to_date — entering")
    try:
        app = state["app_handle"]
        to_date = state.get("to_date") or settings.filter_to_date
        state["to_date"] = to_date
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        _enter_date(main_win, "ToDate", "To Date", to_date)
        logger.info("[Agent3] To date entered: {}", to_date)

    except Exception as exc:
        state["error"] = f"enter_to_date failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "enter_to_date_error")
        except Exception:
            pass

    return state
