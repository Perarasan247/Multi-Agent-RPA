"""Node: Dismiss the XLSX Export Options popup by pressing Enter (OK)."""

from __future__ import annotations

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings

pyautogui.FAILSAFE = False

_EXCEL_FORMATS = {"xlsx", "xls"}


def dismiss_export_popup_node(state: GlobalState) -> GlobalState:
    """Press Enter to dismiss the XLSX Export Options popup.

    The popup appears instantly after clicking XLSX File button
    with OK already focused. Just press Enter.
    For non-Excel formats this node is skipped.
    """
    logger.info("[Agent4] Node: dismiss_export_popup — entering")
    try:
        fmt = settings.download_format.strip().lower()
        if fmt not in _EXCEL_FORMATS:
            logger.info("[Agent4] Format '{}' — no export popup, skipping.", fmt)
            state["export_popup_dismissed"] = True
            return state

        # The popup appears <1s after clicking XLSX button with OK focused.
        # Brief wait for dialog to fully render, then press Enter.
        time.sleep(1.0)
        pyautogui.press("enter")
        logger.info("[Agent4] Pressed Enter to dismiss export options popup.")
        time.sleep(0.5)
        state["export_popup_dismissed"] = True

    except Exception as exc:
        state["error"] = f"dismiss_export_popup failed: {exc}"
        logger.error("[Agent4] {}", state["error"])

    return state
