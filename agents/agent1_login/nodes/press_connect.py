"""Node: Press the Connect button on the login screen."""

import pyautogui
import pygetwindow as gw
from loguru import logger
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_element_info import UIAElementInfo

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import _is_excellon_window
from automation.screenshot import capture_screen, save_debug_screenshot

pyautogui.FAILSAFE = False


def _get_excellon_uia_wrapper():
    """Get a UIA wrapper for the Excellon window by HWND (fast)."""
    for w in gw.getAllWindows():
        if w.title and _is_excellon_window(w.title, settings.app_window_title):
            try:
                return UIAWrapper(UIAElementInfo(w._hWnd))
            except Exception:
                continue
    return None


def press_connect_node(state: GlobalState) -> GlobalState:
    """Find and click the Connect button."""
    logger.info("[Agent1] Node: press_connect — entering")
    try:
        wrapper = _get_excellon_uia_wrapper()
        if wrapper is None:
            state["error"] = "Cannot find Excellon window for Connect button."
            logger.error("[Agent1] {}", state["error"])
            return state

        # Find Connect button via UIA on specific HWND
        for d in wrapper.descendants():
            try:
                if d.element_info.control_type == "Button":
                    txt = (d.window_text() or "").strip().lower()
                    if "connect" in txt:
                        r = d.rectangle()
                        pyautogui.click(r.mid_point().x, r.mid_point().y)
                        state["connect_pressed"] = True
                        logger.info("[Agent1] Connect button pressed.")
                        return state
            except Exception:
                continue

        state["error"] = "Connect button not found on login screen."
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "press_connect_not_found")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"press_connect failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "press_connect_error")
        except Exception:
            pass

    return state
