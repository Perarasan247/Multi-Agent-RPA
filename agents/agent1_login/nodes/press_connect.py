"""Node: Press the Connect button on the login screen."""

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def press_connect_node(state: GlobalState) -> GlobalState:
    """Find and click the Connect button."""
    logger.info("[Agent1] Node: press_connect — entering")
    try:
        app = state["app_handle"]
        main_win = app.top_window()
        buttons = main_win.descendants(control_type="Button")

        connect_btn = None
        for btn in buttons:
            try:
                text = btn.window_text().strip().lower()
                if "connect" in text:
                    connect_btn = btn
                    break
            except Exception:
                continue

        if connect_btn is None:
            state["error"] = "Connect button not found on login screen."
            logger.error("[Agent1] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "press_connect_not_found")
            except Exception:
                pass
            return state

        connect_btn.click_input()
        state["connect_pressed"] = True
        logger.info("[Agent1] Connect button pressed.")

    except Exception as exc:
        state["error"] = f"press_connect failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "press_connect_error")
        except Exception:
            pass

    return state
