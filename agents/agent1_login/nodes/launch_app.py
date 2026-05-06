"""Node: Launch the Excellon application."""

import time
from pathlib import Path

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import is_app_running, launch_app, connect_to_app, focus_window
from automation.screenshot import capture_screen, save_debug_screenshot


def _launch_via_windows_search(search_term: str) -> None:
    """Press Win key, type search_term, OCR-verify result, then press Enter."""
    logger.info("[Agent1] Windows Search fallback — searching for '{}'.", search_term)

    pyautogui.press("win")
    time.sleep(2.0)
    pyautogui.typewrite(search_term, interval=0.05)
    time.sleep(2.5)

    # OCR verify "Excellon" appears somewhere in the search results
    try:
        from vision.ocr_module_finder import find_module_via_ocr
        screen = capture_screen()
        h, w = screen.shape[:2]
        coords = find_module_via_ocr(screen, "Excellon", 0, 0, w, h)
        if coords:
            logger.info("[Agent1] Windows Search: 'Excellon' found on screen — pressing Enter.")
        else:
            logger.warning(
                "[Agent1] Windows Search: 'Excellon' not visible on screen — pressing Enter anyway."
            )
    except Exception as exc:
        logger.debug("[Agent1] Windows Search OCR check error: {}", exc)

    pyautogui.press("enter")
    time.sleep(3.0)


def launch_app_node(state: GlobalState) -> GlobalState:
    """Launch Excellon or connect to an already-running instance.

    Steps:
        1. Check if app is already running.
        2. If running, connect and skip launch.
        3. Launch via app_exe_path; if that fails or times out, fall back to
           Windows Search (Win key → type stem name → Enter).
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
            try:
                focus_window(app, window_title)
            except Exception as exc:
                logger.warning("Could not focus window, continuing: {}", exc)
            time.sleep(1.0)
            logger.info("[Agent1] Node: launch_app — completed (already running)")
            return state

        # ── Primary launch via exe path ───────────────────────────────────────
        primary_ok = True
        try:
            launch_app(settings.app_exe_path)
        except Exception as exc:
            logger.warning(
                "[Agent1] Primary launch raised '{}', will try Windows Search fallback.", exc
            )
            primary_ok = False

        if primary_ok:
            timeout = 30
            start = time.time()
            while time.time() - start < timeout:
                if is_app_running(window_title):
                    logger.info("Application window detected after primary launch.")
                    break
                time.sleep(1.0)
            else:
                logger.warning(
                    "[Agent1] Primary launch timed out after {}s, trying Windows Search fallback.",
                    timeout,
                )
                primary_ok = False

        # ── Windows Search fallback ───────────────────────────────────────────
        if not primary_ok:
            search_term = Path(settings.app_exe_path).stem  # e.g. "Excellon Bajaj 5"
            _launch_via_windows_search(search_term)

            timeout = 30
            start = time.time()
            while time.time() - start < timeout:
                if is_app_running(window_title):
                    logger.info("Application window detected after Windows Search launch.")
                    break
                time.sleep(1.0)
            else:
                state["error"] = (
                    f"Application did not start within {timeout}s after both primary launch "
                    f"and Windows Search fallback. Exe path: {settings.app_exe_path}"
                )
                try:
                    save_debug_screenshot(capture_screen(), "launch_app_timeout")
                except Exception:
                    pass
                logger.error("[Agent1] {}", state["error"])
                return state

        # ── Window is up — give it a moment then connect ──────────────────────
        time.sleep(2.0)

        app = connect_to_app(window_title)
        state["app_handle"] = app
        state["app_launched"] = True
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
