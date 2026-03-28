"""Node: Launch the Excellon application."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import is_app_running, launch_app, connect_to_app, focus_window
from automation.screenshot import capture_screen, save_debug_screenshot


def launch_app_node(state: GlobalState) -> GlobalState:
    """Launch Excellon or connect to an already-running instance.

    Steps:
        1. Check if app is already running.
        2. If running, connect and skip launch.
        3. If not running, launch and poll for window.
        4. Connect to the app and store handle in state.
    """
    logger.info("[Agent1] Node: launch_app — entering")
    try:
        window_title = settings.app_window_title

        # Check if already running
        if is_app_running(window_title):
            logger.info("App already running, connecting and bringing to foreground.")
            app = connect_to_app(window_title)
            state["app_handle"] = app
            state["app_launched"] = True
            # Bring the window to the foreground so it's visible and interactable
            try:
                focus_window(app, window_title)
            except Exception as exc:
                logger.warning("Could not focus window, continuing: {}", exc)
            time.sleep(1.0)
            logger.info("[Agent1] Node: launch_app — completed (already running)")
            return state

        # Launch the application
        launch_app(settings.app_exe_path)

        # Poll for the window to appear
        timeout = 30
        start = time.time()
        while time.time() - start < timeout:
            if is_app_running(window_title):
                logger.info("Application window detected after launch.")
                break
            time.sleep(1.0)
        else:
            state["error"] = (
                f"Application did not start within {timeout}s. "
                f"Exe path: {settings.app_exe_path}"
            )
            try:
                save_debug_screenshot(capture_screen(), "launch_app_timeout")
            except Exception:
                pass
            logger.error("[Agent1] {}", state["error"])
            return state

        # Give the window a moment to initialize
        time.sleep(2.0)

        # Connect
        app = connect_to_app(window_title)
        state["app_handle"] = app
        state["app_launched"] = True
        # Bring the window to the foreground
        try:
            focus_window(app, window_title)
        except Exception as exc:
            logger.warning("Could not focus window, continuing: {}", exc)
        logger.info("[Agent1] Node: launch_app — completed successfully")

    except Exception as exc:
        state["error"] = f"launch_app failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "launch_app_error")
        except Exception:
            pass

    return state
