"""Node: Handle the XLSX Export Options popup.

Steps:
  1. Wait for the popup to appear.
  2. Uncheck 'Export hyperlinks' using a 4-tier fallback:
       Tier 1  UIA (pywinauto UIA backend) — most structured, best for .NET
       Tier 2  Win32 HwndWrapper — native Win32 BM_GETCHECK, reliable for WinForms
       Tier 3  Gemini vision — crops the dialog, asks Gemini for checkbox coords
       Tier 4  Coordinate click — fixed relative offset inside the dialog rectangle
  3. Click OK (or press Enter — OK is focused by default).
"""

from __future__ import annotations

import io
import re
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.screenshot import capture_screen

pyautogui.FAILSAFE = False

_EXCEL_FORMATS = {"xlsx", "xls"}
_POPUP_TITLES  = ("XLSX Export Options", "XLS Export Options", "Export Options")

# Fallback relative position of the "Export hyperlinks" checkbox tick-box
# within the dialog (18% from left, 67% from top).
_CHECKBOX_REL_X = 0.18
_CHECKBOX_REL_Y = 0.67


# ── Find the popup ────────────────────────────────────────────────────────────


def _find_export_popup() -> tuple[int | None, object | None]:
    """Return (hwnd, gw_window) of the export options dialog, or (None, None)."""
    for w in gw.getAllWindows():
        title = w.title or ""
        if any(t in title for t in _POPUP_TITLES):
            return w._hWnd, w
    return None, None


# ── Tier 1: UIA ───────────────────────────────────────────────────────────────


def _uncheck_via_uia(hwnd: int) -> bool:
    try:
        from pywinauto import Application
        app = Application(backend="uia").connect(handle=hwnd)
        dlg = app.window(handle=hwnd)
        for d in dlg.descendants():
            try:
                txt = (d.window_text() or "").strip()
                if "Export hyperlinks" not in txt:
                    continue
                state = d.get_toggle_state()
                if state == 1:
                    d.click_input()
                    time.sleep(0.3)
                    logger.info("[Agent4] [UIA] Unchecked 'Export hyperlinks'.")
                else:
                    logger.info("[Agent4] [UIA] 'Export hyperlinks' already unchecked.")
                return True
            except Exception:
                continue
    except Exception as exc:
        logger.debug("[Agent4] UIA tier failed: {}", exc)
    return False


# ── Tier 2: Win32 HwndWrapper ────────────────────────────────────────────────


def _uncheck_via_win32(hwnd: int) -> bool:
    try:
        from pywinauto.controls.hwndwrapper import HwndWrapper
        dlg = HwndWrapper(hwnd)
        for d in dlg.descendants():
            try:
                txt = (d.window_text() or "").strip()
                if "Export hyperlinks" not in txt:
                    continue
                state = d.get_toggle_state()
                if state == 1:
                    r = d.rectangle()
                    pyautogui.click(r.mid_point().x, r.mid_point().y)
                    time.sleep(0.3)
                    logger.info("[Agent4] [Win32] Unchecked 'Export hyperlinks'.")
                else:
                    logger.info("[Agent4] [Win32] 'Export hyperlinks' already unchecked.")
                return True
            except Exception:
                continue
    except Exception as exc:
        logger.debug("[Agent4] Win32 tier failed: {}", exc)
    return False


# ── Tier 3: Gemini vision ────────────────────────────────────────────────────


def _crop_dialog(gw_win) -> Tuple[Optional[np.ndarray], int, int]:
    """Capture the screen and crop to the dialog bounds. Returns (crop, left, top)."""
    screen = capture_screen()
    left   = max(0, gw_win.left)
    top    = max(0, gw_win.top)
    right  = min(screen.shape[1], gw_win.left + gw_win.width)
    bottom = min(screen.shape[0], gw_win.top  + gw_win.height)
    crop   = screen[top:bottom, left:right]
    return crop, left, top


def _parse_coords(text: str, max_w: int, max_h: int) -> Optional[Tuple[int, int]]:
    m = re.search(r"(\d+)\s+(\d+)", text)
    if not m:
        return None
    x, y = int(m.group(1)), int(m.group(2))
    if 0 <= x <= max_w and 0 <= y <= max_h:
        return x, y
    return None


def _uncheck_via_gemini(gw_win) -> bool:
    try:
        import google.generativeai as genai
        from PIL import Image

        if not settings.gemini_api_key:
            logger.debug("[Agent4] Gemini API key not set — skipping Gemini tier.")
            return False

        crop, dlg_left, dlg_top = _crop_dialog(gw_win)
        if crop is None or crop.size == 0:
            return False

        rh, rw = crop.shape[:2]
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        prompt = (
            "This is a screenshot of an 'XLSX Export Options' dialog box. "
            "Find the checkbox labeled 'Export hyperlinks'. "
            "Return ONLY two integers separated by a space: x y "
            "(pixel coordinates of the center of the checkbox tick-box square itself, "
            "not the label text). "
            "Example reply: 45 210"
        )

        genai.configure(api_key=settings.gemini_api_key)
        model    = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content([pil_img, prompt])
        text     = (response.text or "").strip()

        rel = _parse_coords(text, rw, rh)
        if rel is None:
            logger.warning("[Agent4] [Gemini] Could not parse coords from: {}", text)
            return False

        abs_x = dlg_left + rel[0]
        abs_y = dlg_top  + rel[1]
        pyautogui.click(abs_x, abs_y)
        time.sleep(0.3)
        logger.info(
            "[Agent4] [Gemini] Clicked 'Export hyperlinks' at ({},{}).", abs_x, abs_y
        )
        return True

    except Exception as exc:
        logger.debug("[Agent4] Gemini tier failed: {}", exc)
    return False


# ── Tier 4: Coordinate fallback ──────────────────────────────────────────────


def _uncheck_via_coords(gw_win) -> bool:
    try:
        cx = int(gw_win.left + gw_win.width  * _CHECKBOX_REL_X)
        cy = int(gw_win.top  + gw_win.height * _CHECKBOX_REL_Y)
        pyautogui.click(cx, cy)
        time.sleep(0.3)
        logger.warning(
            "[Agent4] [Coords] Clicked 'Export hyperlinks' area at ({},{}) "
            "(all upper tiers failed — state unknown, clicking to toggle).",
            cx, cy,
        )
        return True
    except Exception as exc:
        logger.debug("[Agent4] Coordinate tier failed: {}", exc)
    return False


# ── Main node ─────────────────────────────────────────────────────────────────


def dismiss_export_popup_node(state: GlobalState) -> GlobalState:
    """Uncheck 'Export hyperlinks' then click OK in the XLSX Export Options popup."""
    logger.info("[Agent4] Node: dismiss_export_popup — entering")
    try:
        fmt = settings.download_format.strip().lower()
        if fmt not in _EXCEL_FORMATS:
            logger.info("[Agent4] Format '{}' — no export popup, skipping.", fmt)
            state["export_popup_dismissed"] = True
            return state

        # Wait up to 5s for the dialog to appear
        hwnd, gw_win = None, None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            hwnd, gw_win = _find_export_popup()
            if hwnd:
                break
            time.sleep(0.3)

        if hwnd:
            if not _uncheck_via_uia(hwnd):
                if not _uncheck_via_win32(hwnd):
                    if not _uncheck_via_gemini(gw_win):
                        _uncheck_via_coords(gw_win)
        else:
            logger.warning("[Agent4] Export Options popup not found — pressing Enter anyway.")

        # OK button has default focus — Enter confirms
        pyautogui.press("enter")
        logger.info("[Agent4] Pressed Enter to confirm export options.")
        time.sleep(0.5)
        state["export_popup_dismissed"] = True

    except Exception as exc:
        state["error"] = f"dismiss_export_popup failed: {exc}"
        logger.error("[Agent4] {}", state["error"])

    return state
