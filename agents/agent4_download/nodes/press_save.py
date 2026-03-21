"""Node: Set filename and press Save in the Save As dialog."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.file_explorer_handler import (
    wait_for_save_dialog,
    set_filename,
    click_save_button,
)
from automation.screenshot import capture_screen, save_debug_screenshot


def press_save_node(state: GlobalState) -> GlobalState:
    """Set the filename and click Save in the dialog.

    Re-fetches the Save dialog if needed, types the filename,
    verifies it, then clicks Save and waits for dialog to close.
    """
    logger.info("[Agent4] Node: press_save — entering")
    try:
        filename = state.get("filename_built")
        if not filename:
            state["error"] = "No filename built — cannot save."
            logger.error("[Agent4] {}", state["error"])
            return state

        # Get the save dialog (should still be open)
        try:
            dialog = wait_for_save_dialog(timeout=5)
        except TimeoutError:
            state["error"] = "Save dialog no longer open when trying to save."
            logger.error("[Agent4] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "press_save_no_dialog")
            except Exception:
                pass
            return state

        # Set filename
        set_filename(dialog, filename)
        time.sleep(0.3)

        # Verify filename field
        try:
            edits = dialog.descendants(control_type="Edit")
            for edit in edits:
                try:
                    val = edit.get_value() or edit.window_text() or ""
                    if filename.replace(".xlsx", "") in val:
                        logger.info("Filename verified in dialog: '{}'", val)
                        break
                except Exception:
                    continue
        except Exception:
            logger.debug("Could not verify filename in dialog.")

        # Click Save
        click_save_button(dialog)

        # Wait for dialog to close
        start = time.time()
        while time.time() - start < 10:
            try:
                dialog.window_text()
                time.sleep(0.5)
            except Exception:
                logger.info("Save dialog closed after saving.")
                break

        state["file_saved"] = True
        logger.info("[Agent4] File saved: {}", filename)

    except Exception as exc:
        state["error"] = f"press_save failed: {exc}"
        logger.error("[Agent4] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "press_save_error")
        except Exception:
            pass

    return state
