"""Node: Click Generate Report and wait for data to load."""

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def _find_generate_button(main_win):
    """Find Generate Report by automation_id, Button type, or DataItem text."""
    win_rect = main_win.rectangle()

    # Strategy 1: automation_id
    for d in main_win.descendants(control_type="Button"):
        try:
            if (d.element_info.automation_id or "") == "GenerateReport":
                return d
        except Exception:
            continue

    # Strategy 2: Button with "generate" in text
    for d in main_win.descendants(control_type="Button"):
        try:
            txt = (d.window_text() or "").strip().lower()
            if "generate" in txt:
                return d
        except Exception:
            continue

    # Strategy 3: Any control with text "Generate Report" in right panel
    for d in main_win.descendants():
        try:
            txt = (d.window_text() or "").strip()
            if "Generate Report" in txt:
                r = d.rectangle()
                if r.left > win_rect.right - 600 and (r.right - r.left) > 10:
                    return d
        except Exception:
            continue

    return None


def press_generate_report_node(state: GlobalState) -> GlobalState:
    """Click 'Generate Report' and wait for data loading to complete."""
    logger.info("[Agent3] Node: press_generate_report — entering")
    try:
        app = state["app_handle"]
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        gen_ctrl = _find_generate_button(main_win)

        if gen_ctrl is None:
            state["error"] = "Generate Report button not found."
            logger.error("[Agent3] {}", state["error"])
            return state

        # Click using pyautogui at the control's coordinates
        r = gen_ctrl.rectangle()
        cx = (r.left + r.right) // 2
        cy = (r.top + r.bottom) // 2
        logger.info("[Agent3] Clicking Generate Report at ({},{}).", cx, cy)
        pyautogui.click(cx, cy)

        # Minimum wait before checking — give Excellon time to fire the query
        MIN_WAIT = 3
        time.sleep(MIN_WAIT)

        # Long-running reports can take several minutes. We poll until
        # the status bar reports "Ready in X Seconds" (data loaded) or
        # data rows appear in the content area. Hard cap at 10 minutes.
        MAX_TIMEOUT_SEC = 600           # 10 minutes — covers heavy reports
        POLL_INTERVAL_SEC = 2.0
        PROGRESS_LOG_INTERVAL_SEC = 30  # tell the user we're still alive

        start = time.time()
        last_progress_log = start
        report_loaded = False

        while time.time() - start < MAX_TIMEOUT_SEC:
            try:
                # Check 0: "No data" popup — click OK and abort
                for d in main_win.descendants(control_type="Text"):
                    try:
                        txt = (d.window_text() or "").strip().lower()
                        if "no data" in txt or "return no data" in txt:
                            logger.warning("[Agent3] 'No data' popup detected.")
                            pyautogui.press("enter")
                            time.sleep(1.0)
                            state["error"] = (
                                "Report returned no data for the selected filters/date range."
                            )
                            logger.error("[Agent3] {}", state["error"])
                            return state
                    except Exception:
                        continue

                # Check 1: Status bar shows "Ready in X Seconds"
                for d in main_win.descendants(control_type="Text"):
                    try:
                        txt = (d.window_text() or "").strip().lower()
                        if "ready in" in txt and "second" in txt:
                            report_loaded = True
                            logger.info(
                                "[Agent3] Status bar: '{}'",
                                d.window_text().strip(),
                            )
                            break
                    except Exception:
                        continue

                if report_loaded:
                    break

                # Check 2: Data rows visible in main content area
                win_rect = main_win.rectangle()
                content_items = 0
                for item in main_win.descendants(control_type="DataItem"):
                    try:
                        ir = item.rectangle()
                        if ir.left < win_rect.right - 400:
                            content_items += 1
                    except Exception:
                        continue
                if content_items > 3:
                    report_loaded = True
                    logger.info(
                        "[Agent3] Report data visible: {} items.", content_items,
                    )
                    break

            except Exception as exc:
                logger.debug("Polling report: {}", exc)

            # Periodic progress log so the user knows we're still waiting
            now = time.time()
            if now - last_progress_log >= PROGRESS_LOG_INTERVAL_SEC:
                elapsed = int(now - start)
                logger.info(
                    "[Agent3] Still waiting for Generate Report to finish... "
                    "({}s elapsed, max {}s)",
                    elapsed, MAX_TIMEOUT_SEC,
                )
                last_progress_log = now

            time.sleep(POLL_INTERVAL_SEC)

        if not report_loaded:
            # FAIL the pipeline — do NOT continue to download a non-existent
            # report. The pipeline-level retry in main.py will try again.
            elapsed = int(time.time() - start)
            state["error"] = (
                f"Generate Report did not finish within {MAX_TIMEOUT_SEC}s "
                f"(waited {elapsed + MIN_WAIT}s total). The query may be "
                f"running too slowly or has hung — refusing to proceed to "
                f"the export step with no data on screen."
            )
            logger.error("[Agent3] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "generate_report_timeout")
            except Exception:
                pass
            return state

        # Settle time — let the UI finish painting after data arrived
        time.sleep(2.0)

        state["report_generated"] = True
        logger.info(
            "[Agent3] Node: press_generate_report — completed in {}s",
            int(time.time() - start) + MIN_WAIT,
        )

    except Exception as exc:
        state["error"] = f"press_generate_report failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "press_generate_report_error")
        except Exception:
            pass

    return state
