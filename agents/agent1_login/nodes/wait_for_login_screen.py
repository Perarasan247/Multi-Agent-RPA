"""Node: Wait for login screen to appear with username/password fields."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def wait_for_login_screen_node(state: GlobalState) -> GlobalState:
    """Poll until the login screen with credential fields is visible.

    Looks for:
        - At least 2 Edit controls (username + password)
        - A 'Connect' button
    """
    logger.info("[Agent1] Node: wait_for_login_screen — entering")
    try:
        app = state["app_handle"]
        timeout = 15
        start = time.time()

        while time.time() - start < timeout:
            try:
                main_win = app.top_window()
                edits = main_win.descendants(control_type="Edit")
                buttons = main_win.descendants(control_type="Button")

                edit_count = len(edits)
                connect_found = False
                for btn in buttons:
                    try:
                        text = btn.window_text().strip().lower()
                        if "connect" in text:
                            connect_found = True
                            break
                    except Exception:
                        continue

                if edit_count >= 2 and connect_found:
                    state["login_screen_ready"] = True
                    logger.info(
                        "[Agent1] Login screen ready: {} edit fields, Connect button found.",
                        edit_count,
                    )
                    return state

                logger.debug(
                    "Waiting for login screen: edits={}, connect={}",
                    edit_count, connect_found,
                )
            except Exception as exc:
                logger.debug("Polling login screen: {}", exc)

            time.sleep(0.5)

        state["error"] = (
            f"Login screen did not appear in {timeout}s. "
            f"Could not find username/password fields and Connect button."
        )
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "login_screen_timeout")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"wait_for_login_screen failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "login_screen_error")
        except Exception:
            pass

    return state
