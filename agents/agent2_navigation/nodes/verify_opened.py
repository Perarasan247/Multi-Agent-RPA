"""Node: Verify the report has opened after clicking."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def verify_opened_node(state: GlobalState) -> GlobalState:
    """Confirm the report window/panel has opened.

    Checks for:
        a. New panel/tab with title matching report_name
        b. Main window title changed to include report_name
        c. New child window with report_name
    """
    logger.info("[Agent2] Node: verify_opened — entering")
    try:
        app = state["app_handle"]
        report_name = state["report_name"]
        timeout = 5
        start = time.time()

        while time.time() - start < timeout:
            try:
                main_win = app.top_window()

                # Check a: main window title
                main_title = main_win.window_text()
                if report_name.lower() in main_title.lower():
                    state["file_opened"] = True
                    logger.info(
                        "[Agent2] Report opened: main title contains '{}'.",
                        report_name,
                    )
                    return state

                # Check b: tab controls
                try:
                    tabs = main_win.descendants(control_type="TabItem")
                    for tab in tabs:
                        try:
                            tab_text = tab.window_text().strip()
                            if report_name.lower() in tab_text.lower():
                                state["file_opened"] = True
                                logger.info(
                                    "[Agent2] Report opened: tab '{}' found.",
                                    tab_text,
                                )
                                return state
                        except Exception:
                            continue
                except Exception:
                    pass

                # Check c: any new pane/window with report name
                try:
                    descendants = main_win.descendants()
                    for desc in descendants:
                        try:
                            text = desc.window_text().strip()
                            ctrl_type = desc.element_info.control_type
                            if (
                                text
                                and report_name.lower() in text.lower()
                                and ctrl_type in ("Pane", "Window", "Document", "Custom")
                            ):
                                state["file_opened"] = True
                                logger.info(
                                    "[Agent2] Report opened: {} '{}' found.",
                                    ctrl_type, text,
                                )
                                return state
                        except Exception:
                            continue
                except Exception:
                    pass

                # Check d: separate windows
                try:
                    all_wins = app.windows()
                    for win in all_wins:
                        try:
                            title = win.window_text().strip()
                            if report_name.lower() in title.lower():
                                state["file_opened"] = True
                                logger.info(
                                    "[Agent2] Report opened: window '{}' found.",
                                    title,
                                )
                                return state
                        except Exception:
                            continue
                except Exception:
                    pass

            except Exception as exc:
                logger.debug("Polling verify_opened: {}", exc)

            time.sleep(0.5)

        state["error"] = (
            f"File did not open after click: '{report_name}'. "
            f"Waited {timeout}s and no matching panel/tab/window found."
        )
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "verify_opened_timeout")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"verify_opened failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "verify_opened_error")
        except Exception:
            pass

    return state
