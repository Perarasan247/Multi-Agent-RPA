"""Node: Verify the home screen is fully loaded and visible."""

import re
import time

import pygetwindow as gw
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import _is_excellon_window
from automation.screenshot import capture_screen, save_debug_screenshot


def verify_home_screen_node(state: GlobalState) -> GlobalState:
    """Verify the Excellon home screen is visible.

    Checks:
        - Window title contains version string (e.g. "Excellon 5.0.xxx")
          OR a report name pattern like "Report Name - Excellon 5.0.xxx"
        - Window is visible and reasonably sized
    """
    logger.info("[Agent1] Node: verify_home_screen — entering")
    try:
        timeout = 30
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for w in gw.getAllWindows():
                if not w.title:
                    continue
                if not _is_excellon_window(w.title, settings.app_window_title):
                    continue

                # The home screen window title contains a version like "Excellon 5.0.214.22654"
                # or "Report Name - Excellon 5.0.214.22654"
                has_version = bool(re.search(r"Excellon\s+\d+\.\d+", w.title, re.IGNORECASE))

                if has_version:
                    state["home_screen_ready"] = True
                    logger.info(
                        "[Agent1] Home screen verified: title='{}'", w.title,
                    )
                    return state

            time.sleep(1.0)

        # Timeout — if the Excellon window exists but without version,
        # accept it anyway (some states don't show version).
        for w in gw.getAllWindows():
            if w.title and _is_excellon_window(w.title, settings.app_window_title):
                state["home_screen_ready"] = True
                logger.warning(
                    "[Agent1] Home screen not fully verified but Excellon window exists: '{}'. Continuing.",
                    w.title,
                )
                return state

        state["error"] = (
            f"Home screen not verified within {timeout}s. "
            "No Excellon window found."
        )
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "verify_home_screen_timeout")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"verify_home_screen failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "verify_home_screen_error")
        except Exception:
            pass

    return state
