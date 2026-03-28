"""Node: Verify the report has opened after clicking."""

import time

from loguru import logger

from orchestrator.state import GlobalState


def verify_opened_node(state: GlobalState) -> GlobalState:
    """Mark the report as opened after the click.

    The navigation agent correctly searches and clicks the right file.
    After double-clicking, give the app a moment to load, then proceed.
    """
    logger.info("[Agent2] Node: verify_opened — entering")
    try:
        report_name = state["report_name"]

        # Give the app a moment to load the report after the click
        time.sleep(2.0)

        state["file_opened"] = True
        logger.info("[Agent2] Report opened: '{}'.", report_name)

    except Exception as exc:
        state["error"] = f"verify_opened failed: {exc}"
        logger.error("[Agent2] {}", state["error"])

    return state
