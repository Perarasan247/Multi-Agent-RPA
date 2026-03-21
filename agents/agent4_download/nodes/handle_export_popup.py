"""Node: Handle the post-export popup ('Open the file?')."""

from loguru import logger

from orchestrator.state import GlobalState
from automation.popup_handler import handle_popup_no, wait_for_popup, get_popup_buttons
from automation.screenshot import capture_screen, save_debug_screenshot


def handle_export_popup_node(state: GlobalState) -> GlobalState:
    """Dismiss the export completion popup by clicking No.

    The popup typically asks whether to open the exported file.
    We click No to decline opening.
    """
    logger.info("[Agent4] Node: handle_export_popup — entering")
    try:
        result = handle_popup_no(timeout=10)

        if result == "no_clicked":
            state["export_popup_closed"] = True
            logger.info("[Agent4] Export popup dismissed with No.")
        elif result == "none_found":
            # Maybe no popup appeared — not necessarily an error
            # Try clicking OK as alternative
            popup = wait_for_popup(timeout=3)
            if popup:
                buttons = get_popup_buttons(popup)
                if "no" in buttons:
                    buttons["no"].click_input()
                    logger.info("Export popup: clicked No (second attempt).")
                elif "ok" in buttons:
                    buttons["ok"].click_input()
                    logger.info("Export popup: clicked OK (No not available).")
                elif "close" in buttons:
                    buttons["close"].click_input()
                    logger.info("Export popup: clicked Close.")
                state["export_popup_closed"] = True
            else:
                # No popup at all — might be fine
                state["export_popup_closed"] = True
                logger.info("[Agent4] No export popup appeared (continuing).")

    except Exception as exc:
        state["error"] = f"handle_export_popup failed: {exc}"
        logger.error("[Agent4] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "handle_export_popup_error")
        except Exception:
            pass

    return state
