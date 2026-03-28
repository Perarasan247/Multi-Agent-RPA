"""Node: Decline the 'Do you want to open this file?' Export popup."""

from __future__ import annotations

import time

import pyautogui
import pygetwindow as gw
from loguru import logger

from orchestrator.state import GlobalState

pyautogui.FAILSAFE = False


def _find_window_by_title(keywords, timeout: float = 10.0):
    """Poll pygetwindow for a window whose title contains any keyword."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for w in gw.getAllWindows():
                if not w.title:
                    continue
                title_lower = w.title.lower()
                if any(kw in title_lower for kw in keywords):
                    return w._hWnd, w.title
        except Exception:
            pass
        time.sleep(0.3)
    return None, None


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


def decline_open_file_node(state: GlobalState) -> GlobalState:
    """Press No on the 'Do you want to open this file?' Export popup."""
    logger.info("[Agent4] Node: decline_open_file — entering")
    try:
        hwnd, title = _find_window_by_title(("export",), timeout=10.0)

        if hwnd is not None:
            logger.info("[Agent4] Found 'open file' popup: '{}'", title)
            if _click_button_in_window(hwnd, ("&No", "No")):
                state["open_file_declined"] = True
                return state
            # Fallback: Tab to No and press Space
            pyautogui.press("tab")
            time.sleep(0.1)
            pyautogui.press("space")
            state["open_file_declined"] = True
            return state

        # No popup appeared — not an error
        state["open_file_declined"] = True
        logger.info("[Agent4] No 'open file' popup appeared (continuing).")

    except Exception as exc:
        state["error"] = f"decline_open_file failed: {exc}"
        logger.error("[Agent4] {}", state["error"])

    return state
