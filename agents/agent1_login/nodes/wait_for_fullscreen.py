"""Node: Wait for the application to reach fullscreen/maximized state."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def wait_for_fullscreen_node(state: GlobalState) -> GlobalState:
    """Poll until the main window is maximized.

    If not maximized after 10s, attempts to maximize manually.
    """
    logger.info("[Agent1] Node: wait_for_fullscreen — entering")
    try:
        app = state["app_handle"]
        timeout = 20
        manual_maximize_at = 10
        start = time.time()
        manual_attempted = False

        while time.time() - start < timeout:
            try:
                main_win = app.top_window()

                # Check if maximized
                try:
                    if main_win.is_maximized():
                        state["fullscreen_ready"] = True
                        logger.info("[Agent1] Window is maximized.")
                        return state
                except Exception:
                    pass

                # Fallback: check window rect vs screen size
                try:
                    import ctypes
                    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
                    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
                    rect = main_win.rectangle()
                    win_w = rect.right - rect.left
                    win_h = rect.bottom - rect.top
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
                        main_win.maximize()
                        manual_attempted = True
                    except Exception as me:
                        logger.warning("Manual maximize failed: {}", me)

            except Exception as exc:
                logger.debug("Polling fullscreen: {}", exc)

            time.sleep(1.0)

        # Timeout — set as ready anyway if window exists
        # The window might just not be maximized but is still usable
        try:
            main_win = app.top_window()
            if main_win.is_visible():
                state["fullscreen_ready"] = True
                logger.warning(
                    "[Agent1] Window not confirmed maximized after {}s, but visible. Continuing.",
                    timeout,
                )
                return state
        except Exception:
            pass

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
