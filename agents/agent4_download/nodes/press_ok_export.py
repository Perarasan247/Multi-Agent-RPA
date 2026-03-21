"""Node: Press OK in the export options popup."""

from loguru import logger

from orchestrator.state import GlobalState
from automation.popup_handler import handle_popup_yes_ok
from automation.screenshot import capture_screen, save_debug_screenshot


def press_ok_export_node(state: GlobalState) -> GlobalState:
    """Click OK in the export options dialog to proceed.

    Uses the popup handler to find and click OK.
    """
    logger.info("[Agent4] Node: press_ok_export — entering")
    try:
        app = state["app_handle"]

        # Try direct approach first: find OK button in current dialogs
        ok_clicked = False
        try:
            from pywinauto import Desktop
            all_windows = Desktop(backend="uia").windows()
            for win in all_windows:
                try:
                    title = win.window_text().strip().lower()
                    buttons = win.descendants(control_type="Button")
                    for btn in buttons:
                        try:
                            text = btn.window_text().strip().lower()
                            if text == "ok":
                                btn.click_input()
                                ok_clicked = True
                                logger.info("Export OK clicked in dialog: '{}'", win.window_text())
                                break
                        except Exception:
                            continue
                    if ok_clicked:
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback to popup handler
        if not ok_clicked:
            result = handle_popup_yes_ok(timeout=5)
            if result == "none_found":
                state["error"] = "Export OK button not found in any dialog."
                logger.error("[Agent4] {}", state["error"])
                try:
                    save_debug_screenshot(capture_screen(), "press_ok_export_not_found")
                except Exception:
                    pass
                return state
            ok_clicked = True

        state["export_ok_pressed"] = True
        logger.info("[Agent4] Export OK pressed.")

    except Exception as exc:
        state["error"] = f"press_ok_export failed: {exc}"
        logger.error("[Agent4] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "press_ok_export_error")
        except Exception:
            pass

    return state
