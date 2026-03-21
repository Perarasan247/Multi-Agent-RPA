"""Node: Handle 0-N popups that appear after pressing Connect."""

from loguru import logger

from orchestrator.state import GlobalState
from automation.popup_handler import dismiss_all_popups
from automation.screenshot import capture_screen, save_debug_screenshot


def handle_popups_pre_node(state: GlobalState) -> GlobalState:
    """Dismiss all pre-fullscreen popups dynamically.

    Known popups:
        - Login Confirmation → YES
        - Application Installation Alert → OK
        - Any other dialog → YES if available, else OK

    Zero popups is a valid outcome (not an error).
    """
    logger.info("[Agent1] Node: handle_popups_pre — entering")
    try:
        count = dismiss_all_popups(max_iterations=5)
        state["pre_popups_cleared"] = True
        logger.info(
            "[Agent1] Pre-login popups handled: {} popup(s) dismissed.",
            count,
        )

    except Exception as exc:
        state["error"] = f"handle_popups_pre failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "handle_popups_pre_error")
        except Exception:
            pass

    return state
