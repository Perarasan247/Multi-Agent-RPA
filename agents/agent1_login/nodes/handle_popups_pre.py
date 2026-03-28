"""Node: Handle 0-N popups that appear after pressing Connect.

Known popups (in order):
    1. Login Confirmation → click Yes
    2. Application Installation Alert → click OK
"""

import time

import pyautogui
import pygetwindow as gw
from loguru import logger
from pywinauto.controls.hwndwrapper import HwndWrapper

from orchestrator.state import GlobalState
from automation.window_manager import _is_excellon_window
from config.settings import settings

pyautogui.FAILSAFE = False

# Titles that are the main Excellon window (not popups)
_MAIN_TITLES = {"excellon"}

# Popup titles we expect and can dismiss
_POPUP_DISMISS = {
    "yes": ("&Yes", "Yes"),
    "ok": ("OK", "&OK", "Ok"),
}


def _find_popup_windows():
    """Find non-main Excellon popup windows using pygetwindow.

    Returns list of (hwnd, title) for popup windows.
    """
    popups = []
    excellon_pid = None

    # Get Excellon PID
    import ctypes
    for w in gw.getAllWindows():
        if w.title and _is_excellon_window(w.title, settings.app_window_title):
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(w._hWnd, ctypes.byref(pid))
            excellon_pid = pid.value
            break

    if excellon_pid is None:
        return popups

    # Find all windows belonging to Excellon process that aren't the main window
    for w in gw.getAllWindows():
        if not w.title or not w.title.strip():
            continue
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(w._hWnd, ctypes.byref(pid))
        if pid.value != excellon_pid:
            continue
        title_lower = w.title.strip().lower()
        # Skip main Excellon window
        if title_lower in _MAIN_TITLES:
            continue
        import re
        if re.match(r"^excellon\s+\d+\.\d+", title_lower):
            continue
        # Skip tiny or invisible windows
        if w.width < 100 or w.height < 40:
            continue
        popups.append((w._hWnd, w.title.strip()))

    return popups


def _click_button_in_popup(hwnd, button_labels) -> bool:
    """Find and click a button in the popup using win32 descendants."""
    try:
        dlg = HwndWrapper(hwnd)
        for d in dlg.descendants():
            try:
                txt = (d.window_text() or "").strip()
                if txt in button_labels:
                    r = d.rectangle()
                    if r.width() > 10:
                        pyautogui.click(r.mid_point().x, r.mid_point().y)
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _dismiss_popup(hwnd, title) -> bool:
    """Dismiss a popup by clicking Yes (preferred) or OK."""
    title_lower = title.lower()

    # Determine button priority based on popup title
    if "confirm" in title_lower or "login" in title_lower:
        labels = ("&Yes", "Yes", "OK", "&OK")
    elif "alert" in title_lower or "install" in title_lower:
        labels = ("OK", "&OK", "Yes", "&Yes")
    else:
        labels = ("&Yes", "Yes", "OK", "&OK", "Close", "&Close")

    if _click_button_in_popup(hwnd, labels):
        logger.info("[Agent1] Dismissed popup '{}' via button.", title)
        return True

    # Fallback: press Enter
    logger.warning("[Agent1] Button not found in '{}', pressing Enter.", title)
    pyautogui.press("enter")
    time.sleep(0.3)
    return True


def handle_popups_pre_node(state: GlobalState) -> GlobalState:
    """Dismiss all pre-fullscreen popups dynamically.

    Polls for popup windows and dismisses them one at a time.
    Zero popups is a valid outcome (not an error).
    """
    logger.info("[Agent1] Node: handle_popups_pre — entering")
    try:
        count = 0
        max_popups = 5

        for i in range(max_popups):
            # Wait for popup to appear (first iteration longer timeout)
            timeout = 10 if i == 0 else 5
            deadline = time.monotonic() + timeout
            popup_found = False

            while time.monotonic() < deadline:
                popups = _find_popup_windows()
                if popups:
                    hwnd, title = popups[0]
                    logger.info("[Agent1] Popup #{} detected: '{}'", i + 1, title)
                    _dismiss_popup(hwnd, title)
                    count += 1
                    popup_found = True
                    time.sleep(1.0)  # wait for popup to close
                    break
                time.sleep(0.3)

            if not popup_found:
                break

        state["pre_popups_cleared"] = True
        logger.info("[Agent1] Pre-login popups handled: {} popup(s) dismissed.", count)

    except Exception as exc:
        state["error"] = f"handle_popups_pre failed: {exc}"
        logger.error("[Agent1] {}", state["error"])

    return state
