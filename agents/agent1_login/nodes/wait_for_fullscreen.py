"""Node: Wait for the application to reach fullscreen/maximized state."""

import ctypes
import time

import pygetwindow as gw
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import _is_excellon_window
from automation.screenshot import capture_screen, save_debug_screenshot


def _find_excellon_gw():
    """Find the Excellon pygetwindow object (fast)."""
    for w in gw.getAllWindows():
        if w.title and _is_excellon_window(w.title, settings.app_window_title):
            return w
    return None


def wait_for_fullscreen_node(state: GlobalState) -> GlobalState:
    """Poll until the main window is maximized."""
    logger.info("[Agent1] Node: wait_for_fullscreen — entering")
    try:
        timeout = 20
        manual_maximize_at = 10
        start = time.time()
        manual_attempted = False

        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)

        while time.time() - start < timeout:
            win = _find_excellon_gw()
            if win is None:
                time.sleep(0.5)
                continue

            # Check if maximized via pygetwindow
            try:
                if win.isMaximized:
                    state["fullscreen_ready"] = True
                    logger.info("[Agent1] Window is maximized.")
                    return state
            except Exception:
                pass

            # Fallback: check window size vs screen size
            try:
                win_w = win.width
                win_h = win.height
                if win_w >= screen_w * 0.95 and win_h >= screen_h * 0.90:
                    state["fullscreen_ready"] = True
                    logger.info(
                        "[Agent1] Window appears fullscreen: {}x{} on {}x{} screen.",
                        win_w, win_h, screen_w, screen_h,
                    )
                    return state
            except Exception:
                pass

            # Try to maximize manually after threshold
            elapsed = time.time() - start
            if elapsed >= manual_maximize_at and not manual_attempted:
                logger.info("Attempting manual maximize after {}s.", int(elapsed))
                try:
                    ctypes.windll.user32.ShowWindow(win._hWnd, 3)  # SW_MAXIMIZE
                    manual_attempted = True
                except Exception as me:
                    logger.warning("Manual maximize failed: {}", me)

            time.sleep(0.5)

        # Timeout — check if window is at least visible
        win = _find_excellon_gw()
        if win is not None and win.visible:
            state["fullscreen_ready"] = True
            logger.warning(
                "[Agent1] Window not confirmed maximized after {}s, but visible. Continuing.",
                timeout,
            )
            return state

        state["error"] = f"Fullscreen state not achieved within {timeout}s."
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "wait_fullscreen_timeout")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"wait_for_fullscreen failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "wait_fullscreen_error")
        except Exception:
            pass

    return state
