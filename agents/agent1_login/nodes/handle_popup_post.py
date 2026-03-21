"""Node: Handle optional popup after fullscreen transition."""

from loguru import logger

from orchestrator.state import GlobalState
from automation.popup_handler import handle_popup_yes_ok
from automation.screenshot import capture_screen, save_debug_screenshot


def handle_popup_post_node(state: GlobalState) -> GlobalState:
    """Handle one optional popup that may appear after fullscreen.

    If no popup appears, this is NOT an error.
    """
    logger.info("[Agent1] Node: handle_popup_post — entering")
    try:
        result = handle_popup_yes_ok(timeout=5)
        state["post_popup_cleared"] = True
        logger.info("[Agent1] Post-fullscreen popup handled: {}", result)

    except Exception as exc:
        state["error"] = f"handle_popup_post failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "handle_popup_post_error")
        except Exception:
            pass

    return state
