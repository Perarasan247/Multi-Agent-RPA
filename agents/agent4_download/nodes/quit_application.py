"""Node: Quit the Excellon application."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import focus_window, is_app_running
from automation.keyboard_mouse import press_hotkey
from automation.popup_handler import handle_popup_yes_ok
from automation.screenshot import capture_screen, save_debug_screenshot


def quit_application_node(state: GlobalState) -> GlobalState:
    """Close the Excellon application gracefully.

    Tries the Exit button first, then falls back to Alt+F4.
    Handles any 'Are you sure?' confirmation popup.
    """
    logger.info("[Agent4] Node: quit_application — entering")
    try:
        app = state["app_handle"]

        # Focus the window
        try:
            focus_window(app, settings.app_window_title)
        except Exception:
            pass

        main_win = app.top_window()
        exit_clicked = False

        # Strategy 1: Find Exit button in toolbar
        try:
            buttons = main_win.descendants(control_type="Button")
            for btn in buttons:
                try:
                    text = btn.window_text().strip().lower()
                    if "exit" in text or "quit" in text or "close" in text:
                        btn.click_input()
                        exit_clicked = True
                        logger.info("Exit button clicked: '{}'", btn.window_text())
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Strategy 2: Menu item
        if not exit_clicked:
            try:
                menu_items = main_win.descendants(control_type="MenuItem")
                for item in menu_items:
                    try:
                        text = item.window_text().strip().lower()
                        if "exit" in text or "quit" in text:
                            item.click_input()
                            exit_clicked = True
                            logger.info("Exit menu item clicked.")
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        # Strategy 3: Alt+F4
        if not exit_clicked:
            logger.info("Using Alt+F4 to close application.")
            press_hotkey("alt", "F4")
            exit_clicked = True

        # Handle "Are you sure?" confirmation
        time.sleep(1.0)
        handle_popup_yes_ok(timeout=5)

        # Verify process is gone
        start = time.time()
        while time.time() - start < 5:
            if not is_app_running(settings.app_window_title):
                state["app_quit"] = True
                logger.info("[Agent4] Application quit successfully. Pipeline complete.")
                return state
            time.sleep(1.0)

        # App might still be closing
        state["app_quit"] = True
        logger.warning("[Agent4] App may still be closing, but proceeding.")

    except Exception as exc:
        state["error"] = f"quit_application failed: {exc}"
        logger.error("[Agent4] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "quit_application_error")
        except Exception:
            pass

    return state
