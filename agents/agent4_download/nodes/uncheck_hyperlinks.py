"""Node: Uncheck the 'Export Hyperlinks' checkbox in export options."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.popup_handler import wait_for_popup
from automation.screenshot import capture_screen, save_debug_screenshot


def uncheck_hyperlinks_node(state: GlobalState) -> GlobalState:
    """Wait for export options popup, then uncheck Export Hyperlinks.

    If the checkbox is already unchecked, no action is taken.
    """
    logger.info("[Agent4] Node: uncheck_hyperlinks — entering")
    try:
        # Wait for export options dialog
        timeout = 10
        start = time.time()
        export_dialog = None

        app = state["app_handle"]

        while time.time() - start < timeout:
            try:
                # Look for any new dialog/window with export-related content
                from pywinauto import Desktop
                all_windows = Desktop(backend="uia").windows()
                for win in all_windows:
                    try:
                        title = win.window_text().strip().lower()
                        if "export" in title or "option" in title:
                            export_dialog = win
                            break
                        # Check for checkboxes inside the window
                        cbs = win.descendants(control_type="CheckBox")
                        for cb in cbs:
                            try:
                                cb_text = cb.window_text().strip().lower()
                                if "hyperlink" in cb_text:
                                    export_dialog = win
                                    break
                            except Exception:
                                continue
                        if export_dialog:
                            break
                    except Exception:
                        continue
                if export_dialog:
                    break
            except Exception:
                pass
            time.sleep(0.5)

        if export_dialog is None:
            # Maybe the dialog is part of the main window
            try:
                main_win = app.top_window()
                cbs = main_win.descendants(control_type="CheckBox")
                for cb in cbs:
                    try:
                        cb_text = cb.window_text().strip().lower()
                        if "hyperlink" in cb_text:
                            export_dialog = main_win
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if export_dialog is None:
            state["error"] = (
                f"Export options popup not found within {timeout}s."
            )
            logger.error("[Agent4] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "uncheck_hyperlinks_timeout")
            except Exception:
                pass
            return state

        # Find the hyperlinks checkbox
        hyperlink_cb = None
        try:
            checkboxes = export_dialog.descendants(control_type="CheckBox")
            for cb in checkboxes:
                try:
                    text = cb.window_text().strip().lower()
                    if "hyperlink" in text or "hyper link" in text:
                        hyperlink_cb = cb
                        break
                except Exception:
                    continue
        except Exception:
            pass

        if hyperlink_cb is None:
            state["error"] = "Export Hyperlinks checkbox not found in export dialog."
            logger.error("[Agent4] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "hyperlink_cb_not_found")
            except Exception:
                pass
            return state

        # Check current state and uncheck if needed
        is_checked = False
        try:
            toggle_state = hyperlink_cb.get_toggle_state()
            is_checked = toggle_state == 1
        except Exception:
            try:
                legacy = hyperlink_cb.legacy_properties()
                state_val = legacy.get("State", 0)
                is_checked = bool(state_val & 0x10)
            except Exception:
                is_checked = True  # Assume checked, click to be safe

        if is_checked:
            hyperlink_cb.click_input()
            time.sleep(0.3)
            logger.info("Export Hyperlinks checkbox unchecked.")
        else:
            logger.info("Export Hyperlinks checkbox already unchecked.")

        # Verify unchecked
        try:
            toggle_state = hyperlink_cb.get_toggle_state()
            if toggle_state == 0:
                logger.info("Verified: Export Hyperlinks is unchecked.")
            else:
                logger.warning("Export Hyperlinks may still be checked (state={}).", toggle_state)
        except Exception:
            pass

        state["hyperlinks_unchecked"] = True
        logger.info("[Agent4] Node: uncheck_hyperlinks — completed")

    except Exception as exc:
        state["error"] = f"uncheck_hyperlinks failed: {exc}"
        logger.error("[Agent4] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "uncheck_hyperlinks_error")
        except Exception:
            pass

    return state
