"""Node: Gracefully close the Excellon application."""

from __future__ import annotations

import time

import pyautogui
import pygetwindow as gw
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import is_app_running, _is_excellon_window

pyautogui.FAILSAFE = False


def _force_foreground() -> bool:
    """Bring Excellon to foreground."""
    import ctypes

    user32 = ctypes.windll.user32
    all_windows = gw.getAllWindows()
    matches = [w for w in all_windows
               if w.title and _is_excellon_window(w.title, settings.app_window_title)]
    matches.sort(key=lambda w: len(w.title), reverse=True)

    for w in matches:
        try:
            hwnd = w._hWnd
            fore = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
            target = user32.GetWindowThreadProcessId(hwnd, None)
            if fore != target:
                user32.AttachThreadInput(fore, target, True)
            user32.keybd_event(0x12, 0, 0, 0)
            user32.ShowWindow(hwnd, 3)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)
            if fore != target:
                user32.AttachThreadInput(fore, target, False)
            time.sleep(0.3)
            return True
        except Exception:
            continue
    return False


def _click_button_in_window(hwnd, labels) -> bool:
    """Find and click a button in a window using win32 wrapper."""
    from pywinauto.controls.hwndwrapper import HwndWrapper
    dlg = HwndWrapper(hwnd)
    try:
        for d in dlg.descendants():
            txt = (d.window_text() or "").strip()
            if txt in labels:
                r = d.rectangle()
                if r.width() > 10:
                    pyautogui.click(r.mid_point().x, r.mid_point().y)
                    logger.info("[Agent4] Clicked '{}' at ({}, {}).", txt,
                                r.mid_point().x, r.mid_point().y)
                    return True
    except Exception:
        pass
    return False


def _dismiss_confirmation() -> bool:
    """Handle exit confirmation popup via pygetwindow + win32."""
    try:
        for w in gw.getAllWindows():
            if not w.title:
                continue
            title_lower = w.title.lower()
            if any(kw in title_lower for kw in ("confirm", "exit", "close", "quit", "sure")):
                logger.info("[Agent4] Found exit confirmation: '{}'", w.title)
                if _click_button_in_window(w._hWnd, ("&Yes", "Yes", "OK", "&OK")):
                    return True
                # Fallback
                pyautogui.press("enter")
                return True
    except Exception:
        pass
    return False


def close_application_node(state: GlobalState) -> GlobalState:
    """Close Excellon gracefully using Alt+F4 and handle confirmation popups."""
    logger.info("[Agent4] Node: close_application — entering")
    try:
        _force_foreground()
        time.sleep(0.3)

        pyautogui.hotkey("alt", "F4")
        logger.info("[Agent4] Sent Alt+F4.")

        # Handle confirmation popup(s)
        time.sleep(0.5)
        _dismiss_confirmation()
        time.sleep(0.5)
        _dismiss_confirmation()

        # Verify process is gone
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if not is_app_running(settings.app_window_title):
                state["app_closed"] = True
                logger.info("[Agent4] Excellon closed successfully.")
                return state
            time.sleep(0.5)

        state["app_closed"] = True
        logger.warning("[Agent4] Excellon may still be closing, proceeding.")

    except Exception as exc:
        state["error"] = f"close_application failed: {exc}"
        logger.error("[Agent4] {}", state["error"])

    return state
