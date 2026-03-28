"""Node: Handle the Save As dialog — rename file, navigate, and save."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pyautogui
import pygetwindow as gw
from loguru import logger
from pywinauto import Application

from orchestrator.state import GlobalState
from config.settings import settings

pyautogui.FAILSAFE = False


def _find_window_by_title(keywords, timeout: float = 15.0):
    """Poll pygetwindow for a window whose title contains any keyword.

    Returns (hwnd, title) or (None, None).
    """
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


def _wrap_hwnd(hwnd):
    """Create a pywinauto wrapper from a window handle."""
    from pywinauto.controls.hwndwrapper import HwndWrapper
    return HwndWrapper(hwnd)


def _wrap_hwnd_uia(hwnd):
    """Create a UIA wrapper from a window handle."""
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_element_info import UIAElementInfo
    return UIAWrapper(UIAElementInfo(hwnd))


def _find_filename_edit(dlg):
    """Locate the filename text box inside the Save As dialog."""
    attempts = [
        lambda: dlg.child_window(class_name="ComboBoxEx32", found_index=0)
                   .child_window(class_name="ComboBox")
                   .child_window(class_name="Edit"),
        lambda: dlg.child_window(class_name="Edit", found_index=0),
    ]
    for i, fn in enumerate(attempts):
        try:
            elem = fn()
            if elem.exists(timeout=1):
                logger.info("[Agent4] Filename edit found (approach {})", i + 1)
                return elem
        except Exception:
            continue

    # Last resort: iterate descendants for any Edit control
    try:
        for d in dlg.descendants():
            try:
                if d.friendly_class_name() == "Edit":
                    return d
            except Exception:
                continue
    except Exception:
        pass
    return None


def _click_button_in_window(hwnd, labels) -> bool:
    """Find and click a button in a window using win32 wrapper."""
    dlg = _wrap_hwnd(hwnd)
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


def _dismiss_overwrite_popup():
    """Handle 'Confirm Save As' / overwrite dialog → click Yes."""
    hwnd, title = _find_window_by_title(("confirm", "overwrite", "replace"), timeout=3.0)
    if hwnd is None:
        return False
    logger.info("[Agent4] Found overwrite dialog: '{}'", title)
    if _click_button_in_window(hwnd, ("&Yes", "Yes", "OK", "&OK")):
        return True
    # Fallback
    pyautogui.press("enter")
    return True


def handle_save_as_node(state: GlobalState) -> GlobalState:
    """Wait for Save As dialog, rename the file, and save."""
    logger.info("[Agent4] Node: handle_save_as — entering")
    try:
        hwnd, title = _find_window_by_title(("save as",), timeout=15.0)
        if hwnd is None:
            state["error"] = "Save As dialog did not appear within 15s."
            logger.error("[Agent4] {}", state["error"])
            return state

        logger.info("[Agent4] Found Save As dialog: '{}'", title)

        # Use win32 backend wrapper for the Save As dialog (fast, reliable)
        save_as = _wrap_hwnd(hwnd)
        try:
            save_as.set_focus()
        except Exception:
            pass
        time.sleep(0.3)

        edit = _find_filename_edit(save_as)
        if edit is None:
            state["error"] = "Cannot find filename edit box in Save As dialog."
            logger.error("[Agent4] {}", state["error"])
            return state

        # Read original filename
        original = (edit.window_text() or "Report").strip()
        ext = state.get("download_extension", ".xlsx")
        if original.lower().endswith(ext):
            original = original[: -len(ext)]
        logger.info("[Agent4] Original filename: '{}'", original)

        # Build new filename
        date_str = datetime.now().strftime("%d-%m-%Y")
        from_date = state.get("from_date", settings.filter_from_date).replace("/", "-")
        to_date = state.get("to_date", settings.filter_to_date).replace("/", "-")
        report_key = state.get("report_key", settings.report_key)

        new_name = (
            f"{date_str}, {settings.dealer_code}, {settings.branch_code}, "
            f"{report_key}, {from_date} to {to_date}"
        )
        save_dir = settings.save_path
        full_path = str(Path(save_dir) / new_name)
        logger.info("[Agent4] Saving to: '{}'", full_path)

        Path(save_dir).mkdir(parents=True, exist_ok=True)

        # Type full path into filename box
        edit.click_input()
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        edit.type_keys(full_path, with_spaces=True, with_tabs=False)
        time.sleep(0.3)

        state["filename_built"] = new_name + ext

        # Click Save button
        if not _click_button_in_window(hwnd, ("Save", "&Save", "S&ave")):
            logger.warning("[Agent4] Save button not found — pressing Enter.")
            pyautogui.press("enter")
        time.sleep(1.0)

        # Handle overwrite popup if file already exists
        _dismiss_overwrite_popup()

        state["file_saved"] = True
        logger.info("[Agent4] File saved: {}", state["filename_built"])

    except Exception as exc:
        state["error"] = f"handle_save_as failed: {exc}"
        logger.error("[Agent4] {}", state["error"])

    return state
