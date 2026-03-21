"""Node: Click the matched report item to open it."""

import time
import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.keyboard_mouse import scroll_element_into_view
from automation.screenshot import capture_screen, save_debug_screenshot


def click_item_node(state: GlobalState) -> GlobalState:
    """Click the exact-matched tree item to open the report.

    Uses UIA element click when available; falls back to pyautogui
    coordinate click for screenshot-based candidates.
    """
    logger.info("[Agent2] Node: click_item — entering")
    try:
        exact_match = state["exact_match"]
        element = exact_match.get("element")
        report_name = state["report_name"]

        if element is not None:
            # UIA-based click
            scroll_element_into_view(element)
            element.click_input()
            logger.info("[Agent2] UIA click on: '{}'", report_name)
        else:
            # Coordinate-based click (screenshot fallback)
            sx = exact_match.get("screen_x")
            sy = exact_match.get("screen_y")
            if sx is None or sy is None:
                state["error"] = "click_item: no element and no screen coordinates."
                logger.error("[Agent2] {}", state["error"])
                return state
            pyautogui.moveTo(sx, sy, duration=0.2)
            time.sleep(0.1)
            pyautogui.doubleClick(sx, sy)
            logger.info("[Agent2] Coordinate double-click on '{}' at ({}, {}).", report_name, sx, sy)

    except Exception as exc:
        state["error"] = f"click_item failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_item_error")
        except Exception:
            pass

    return state
