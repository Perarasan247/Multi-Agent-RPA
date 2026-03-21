"""Node: Click Generate Report and wait for data to load."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def press_generate_report_node(state: GlobalState) -> GlobalState:
    """Click 'Generate Report' and wait for data loading to complete.

    Polls up to 60s for the report grid to populate or the
    loading indicator to disappear.
    """
    logger.info("[Agent3] Node: press_generate_report — entering")
    try:
        app = state["app_handle"]
        main_win = app.top_window()

        # Find Generate Report button
        gen_btn = None
        buttons = main_win.descendants(control_type="Button")
        for btn in buttons:
            try:
                text = btn.window_text().strip().lower()
                if "generate" in text and "report" in text:
                    gen_btn = btn
                    break
                if "generate" in text:
                    gen_btn = btn
                    break
            except Exception:
                continue

        if gen_btn is None:
            state["error"] = "Generate Report button not found."
            logger.error("[Agent3] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "generate_btn_not_found")
            except Exception:
                pass
            return state

        gen_btn.click_input()
        logger.info("Generate Report button clicked.")

        # Smart wait for report data
        timeout = 60
        start = time.time()
        report_loaded = False

        while time.time() - start < timeout:
            try:
                # Check for data grid / table / rows
                data_grids = main_win.descendants(control_type="DataGrid")
                tables = main_win.descendants(control_type="Table")
                data_items = main_win.descendants(control_type="DataItem")

                if data_grids or tables:
                    # Check if any have children (actual data rows)
                    for grid in data_grids + tables:
                        try:
                            children = grid.children()
                            if len(children) > 1:  # Header + at least 1 row
                                report_loaded = True
                                logger.info(
                                    "Report data loaded: {} rows in grid.",
                                    len(children) - 1,
                                )
                                break
                        except Exception:
                            continue

                if report_loaded:
                    break

                if data_items and len(data_items) > 0:
                    report_loaded = True
                    logger.info(
                        "Report data loaded: {} data items found.",
                        len(data_items),
                    )
                    break

                # Check if Generate button is re-enabled (loading finished)
                try:
                    if gen_btn.is_enabled():
                        elapsed = time.time() - start
                        if elapsed > 3:  # Give at least 3s for loading
                            report_loaded = True
                            logger.info(
                                "Generate button re-enabled after {:.1f}s — assuming loaded.",
                                elapsed,
                            )
                            break
                except Exception:
                    pass

            except Exception as exc:
                logger.debug("Polling report generation: {}", exc)

            time.sleep(1.0)

        if not report_loaded:
            state["error"] = (
                f"Report generation timed out after {timeout}s. "
                "No data grid or table found in the report area."
            )
            logger.error("[Agent3] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "generate_report_timeout")
            except Exception:
                pass
            return state

        state["report_generated"] = True
        logger.info("[Agent3] Node: press_generate_report — completed successfully")

    except Exception as exc:
        state["error"] = f"press_generate_report failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "press_generate_report_error")
        except Exception:
            pass

    return state
