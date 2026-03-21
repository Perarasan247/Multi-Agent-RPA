"""Node: Focus the Excellon application window."""

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import focus_window as wm_focus_window, connect_to_app
from automation.screenshot import capture_screen, save_debug_screenshot


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def _focus_with_retry(app, title: str) -> bool:
    """Focus window with tenacity retry."""
    return wm_focus_window(app, title)


def focus_window_node(state: GlobalState) -> GlobalState:
    """Bring the Excellon window to the foreground.

    Uses the app_handle from Agent 1 if available, otherwise connects
    to the already-running Excellon application (standalone agent mode).
    Retries up to 3 times with 2s waits.
    """
    logger.info("[Agent2] Node: focus_window — entering")
    try:
        app = state.get("app_handle")
        title = settings.app_window_title

        if app is None:
            logger.info("[Agent2] No app_handle in state — connecting to running Excellon window.")
            app = connect_to_app(title)
            state["app_handle"] = app

        result = _focus_with_retry(app, title)
        if result:
            logger.info("[Agent2] Window focused successfully.")
        else:
            state["error"] = f"Failed to focus window '{title}' after retries."
            logger.error("[Agent2] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "focus_window_failed")
            except Exception:
                pass

    except Exception as exc:
        state["error"] = f"focus_window failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "focus_window_error")
        except Exception:
            pass

    return state
