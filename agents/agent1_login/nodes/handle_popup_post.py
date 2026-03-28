"""Node: Handle optional popup after fullscreen transition.

Known popups: HSRP Compliance, Spare Fund, or any other alert.
"""

import re
import time

import pyautogui
import pygetwindow as gw
from loguru import logger
from pywinauto.controls.hwndwrapper import HwndWrapper

from orchestrator.state import GlobalState
from automation.window_manager import _is_excellon_window
from config.settings import settings

pyautogui.FAILSAFE = False


def _find_popup_windows():
    """Find non-main Excellon popup windows using pygetwindow."""
    import ctypes

    popups = []
    excellon_pid = None

    for w in gw.getAllWindows():
        if w.title and _is_excellon_window(w.title, settings.app_window_title):
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(w._hWnd, ctypes.byref(pid))
            excellon_pid = pid.value
            break

    if excellon_pid is None:
        return popups

    for w in gw.getAllWindows():
        if not w.title or not w.title.strip():
            continue
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(w._hWnd, ctypes.byref(pid))
        if pid.value != excellon_pid:
            continue
        title_lower = w.title.strip().lower()
        if title_lower == "excellon":
            continue
        if re.match(r"^excellon\s+\d+\.\d+", title_lower):
            continue
        if re.search(r"- excellon\s+\d+\.\d+", title_lower):
            continue
        if w.width < 100 or w.height < 40:
            continue
        popups.append((w._hWnd, w.title.strip()))

    return popups


def _dismiss_popup(hwnd, title) -> bool:
    """Dismiss a popup by clicking Yes/OK/Close."""
    labels = ("&Yes", "Yes", "OK", "&OK", "Close", "&Close")
    try:
        dlg = HwndWrapper(hwnd)
        for d in dlg.descendants():
            try:
                txt = (d.window_text() or "").strip()
                if txt in labels:
                    r = d.rectangle()
                    if r.width() > 10:
                        pyautogui.click(r.mid_point().x, r.mid_point().y)
                        logger.info("[Agent1] Dismissed post-popup '{}' via '{}'.", title, txt)
                        return True
            except Exception:
                continue
    except Exception:
        pass

    # Fallback
    pyautogui.press("enter")
    logger.warning("[Agent1] Pressed Enter to dismiss '{}'.", title)
    return True


def handle_popup_post_node(state: GlobalState) -> GlobalState:
    """Handle optional popup(s) that may appear after fullscreen.

    If no popup appears, this is NOT an error.
    """
    logger.info("[Agent1] Node: handle_popup_post — entering")
    try:
        count = 0

        for i in range(3):
            timeout = 10 if i == 0 else 5
            deadline = time.monotonic() + timeout
            popup_found = False

            while time.monotonic() < deadline:
                popups = _find_popup_windows()
                if popups:
                    hwnd, title = popups[0]
                    logger.info("[Agent1] Post-popup #{} detected: '{}'", i + 1, title)
                    _dismiss_popup(hwnd, title)
                    count += 1
                    popup_found = True
                    time.sleep(1.0)
                    break
                time.sleep(0.3)

            if not popup_found:
                break

        state["post_popup_cleared"] = True
        logger.info("[Agent1] Post-fullscreen popups handled: {} dismissed.", count)

    except Exception as exc:
        state["error"] = f"handle_popup_post failed: {exc}"
        logger.error("[Agent1] {}", state["error"])

    return state
