"""Node: Click the export button (XLSX/CSV/PDF etc.) in the top toolbar."""

from __future__ import annotations

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import get_main_window, _is_excellon_window

pyautogui.FAILSAFE = False

# Maps DOWNLOAD_FORMAT → toolbar button label and file extension
FORMAT_MAP = {
    "xlsx": {"label": "XLSX File", "extension": ".xlsx"},
    "xls":  {"label": "XLS File",  "extension": ".xls"},
    "csv":  {"label": "CSV File",  "extension": ".csv"},
    "pdf":  {"label": "PDF File",  "extension": ".pdf"},
    "html": {"label": "HTML File", "extension": ".html"},
    "mht":  {"label": "MHT File",  "extension": ".mht"},
    "rtf":  {"label": "RTF File",  "extension": ".rtf"},
    "text": {"label": "Text File", "extension": ".txt"},
    "txt":  {"label": "Text File", "extension": ".txt"},
    "image":{"label": "Image File","extension": ".png"},
}


def _force_foreground() -> bool:
    """Bring the Excellon report window to foreground (maximized).

    Uses AttachThreadInput + ALT key trick to bypass Windows 10
    focus-stealing prevention.
    """
    import ctypes
    import pygetwindow as gw

    user32 = ctypes.windll.user32
    all_windows = gw.getAllWindows()
    matches = [w for w in all_windows
               if w.title and _is_excellon_window(w.title, settings.app_window_title)]
    matches.sort(key=lambda w: len(w.title), reverse=True)

    for w in matches:
        try:
            hwnd = w._hWnd
            fore_thread = user32.GetWindowThreadProcessId(
                user32.GetForegroundWindow(), None)
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            if fore_thread != target_thread:
                user32.AttachThreadInput(fore_thread, target_thread, True)
            user32.keybd_event(0x12, 0, 0, 0)
            user32.ShowWindow(hwnd, 3)  # SW_SHOWMAXIMIZED
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)
            if fore_thread != target_thread:
                user32.AttachThreadInput(fore_thread, target_thread, False)
            time.sleep(0.5)
            logger.info("[Agent4] Forced foreground: '{}'", w.title)
            return True
        except Exception as e:
            logger.warning("[Agent4] Foreground failed: {}", e)
    return False


def click_export_button_node(state: GlobalState) -> GlobalState:
    """Click the export button matching DOWNLOAD_FORMAT on the toolbar.

    Uses child_window() targeted UIA search (bounded, won't hang).
    Falls back to descendant midpoint click.
    """
    logger.info("[Agent4] Node: click_export_button — entering")
    try:
        app = state["app_handle"]
        fmt = settings.download_format.strip().lower()
        fmt_info = FORMAT_MAP.get(fmt)

        if fmt_info is None:
            state["error"] = (
                f"Unsupported download format '{fmt}'. "
                f"Supported: {', '.join(FORMAT_MAP.keys())}"
            )
            logger.error("[Agent4] {}", state["error"])
            return state

        button_label = fmt_info["label"]
        extension = fmt_info["extension"]
        state["download_extension"] = extension

        # Bring Excellon to front
        _force_foreground()
        time.sleep(1.0)

        main_win = get_main_window(app, settings.app_window_title)

        # Strategy 1: child_window() targeted search (bounded, won't hang)
        for ctype in ("Button", "Hyperlink", "Text", "ListItem", "MenuItem"):
            try:
                elem = main_win.child_window(
                    title=button_label, control_type=ctype, found_index=0
                )
                if elem.exists(timeout=3):
                    elem.click_input()
                    logger.info("[Agent4] Clicked '{}' via child_window ({})",
                                button_label, ctype)
                    state["export_clicked"] = True
                    return state
            except Exception:
                continue

        # Strategy 2: Descendant scan with rectangle midpoint click
        try:
            for d in main_win.descendants():
                txt = (d.window_text() or "").strip()
                if txt == button_label:
                    r = d.rectangle()
                    if r.width() > 5 and r.height() > 5:
                        cx, cy = r.mid_point().x, r.mid_point().y
                        pyautogui.click(cx, cy)
                        logger.info("[Agent4] Clicked '{}' at ({}, {}) via descendant scan",
                                    button_label, cx, cy)
                        state["export_clicked"] = True
                        return state
        except Exception as e:
            logger.warning("[Agent4] Descendant scan failed: {}", e)

        state["error"] = f"'{button_label}' button not found on toolbar."
        logger.error("[Agent4] {}", state["error"])

    except Exception as exc:
        state["error"] = f"click_export_button failed: {exc}"
        logger.error("[Agent4] {}", state["error"])

    return state
