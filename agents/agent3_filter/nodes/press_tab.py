"""Node: Press Tab to move focus to the From Date field."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.keyboard_mouse import press_key


def press_tab_node(state: GlobalState) -> GlobalState:
    """Press Tab key to advance focus to the From Date field."""
    logger.info("[Agent3] Node: press_tab — entering")
    try:
        press_key("tab")
        time.sleep(0.3)
        logger.info("[Agent3] Tab pressed to move to date field.")

    except Exception as exc:
        state["error"] = f"press_tab failed: {exc}"
        logger.error("[Agent3] {}", state["error"])

    return state
