"""Node: Handle the Windows Save As file explorer dialog."""

from pathlib import Path

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.file_explorer_handler import (
    wait_for_save_dialog,
    navigate_to_folder,
)
from automation.screenshot import capture_screen, save_debug_screenshot


def handle_file_explorer_node(state: GlobalState) -> GlobalState:
    """Wait for Save As dialog and navigate to the target folder.

    Navigates to settings.save_path. Errors if folder does not exist
    (folder must be pre-created).
    """
    logger.info("[Agent4] Node: handle_file_explorer — entering")
    try:
        save_path = settings.save_path

        # Wait for Save dialog
        try:
            dialog = wait_for_save_dialog(timeout=15)
        except TimeoutError as te:
            state["error"] = str(te)
            logger.error("[Agent4] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "save_dialog_timeout")
            except Exception:
                pass
            return state

        # Navigate to the save folder
        navigate_to_folder(dialog, save_path)
        logger.info("[Agent4] Navigated to save location: {}", save_path)

    except Exception as exc:
        state["error"] = f"handle_file_explorer failed: {exc}"
        logger.error("[Agent4] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "handle_file_explorer_error")
        except Exception:
            pass

    return state
