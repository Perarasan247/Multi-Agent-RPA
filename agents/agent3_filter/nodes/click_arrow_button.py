"""Node: Click the filter toggle/arrow button to open the filter panel."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def click_arrow_button_node(state: GlobalState) -> GlobalState:
    """Find and click the filter expand/toggle button.

    Searches for arrow/expand button at the bottom-right of the
    report content area, then verifies the filter panel opened.
    """
    logger.info("[Agent3] Node: click_arrow_button — entering")
    try:
        app = state["app_handle"]
        main_win = app.top_window()

        # Strategy 1: Button with arrow-like text
        filter_btn = None
        buttons = main_win.descendants(control_type="Button")
        for btn in buttons:
            try:
                text = btn.window_text().strip()
                auto_id = (btn.element_info.automation_id or "").lower()
                if text in ("▶", ">", ">>", "Show Filter", "Filter", "►"):
                    filter_btn = btn
                    break
                if "filter" in auto_id or "toggle" in auto_id or "expand" in auto_id:
                    filter_btn = btn
                    break
            except Exception:
                continue

        # Strategy 2: Look in bottom-right quadrant
        if filter_btn is None:
            try:
                win_rect = main_win.rectangle()
                mid_x = (win_rect.left + win_rect.right) // 2
                mid_y = (win_rect.top + win_rect.bottom) // 2
                for btn in buttons:
                    try:
                        rect = btn.rectangle()
                        if rect.left > mid_x and rect.top > mid_y:
                            text = btn.window_text().strip()
                            if len(text) <= 3 or "filter" in text.lower():
                                filter_btn = btn
                                break
                    except Exception:
                        continue
            except Exception:
                pass

        # Strategy 3: ToggleButton control type
        if filter_btn is None:
            try:
                toggles = main_win.descendants(control_type="ToggleButton")
                for tb in toggles:
                    try:
                        auto_id = (tb.element_info.automation_id or "").lower()
                        if "filter" in auto_id:
                            filter_btn = tb
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if filter_btn is None:
            state["error"] = (
                "Filter toggle button not found. Tried arrow text, "
                "AutomationId, and positional search."
            )
            logger.error("[Agent3] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "click_arrow_not_found")
            except Exception:
                pass
            return state

        filter_btn.click_input()
        logger.info("Filter toggle button clicked: '{}'", filter_btn.window_text())

        # Verify filter panel opened by looking for Date Range dropdown
        timeout = 10
        start = time.time()
        while time.time() - start < timeout:
            try:
                combos = main_win.descendants(control_type="ComboBox")
                for combo in combos:
                    try:
                        name = (combo.element_info.name or "").lower()
                        text = combo.window_text().lower()
                        if "date" in name or "range" in name or "date" in text:
                            state["filter_window_open"] = True
                            logger.info("[Agent3] Filter panel confirmed open (Date Range found).")
                            return state
                    except Exception:
                        continue

                # Also check for Edit fields that might be date inputs
                edits = main_win.descendants(control_type="Edit")
                date_edits = 0
                for edit in edits:
                    try:
                        name = (edit.element_info.name or "").lower()
                        if "date" in name or "from" in name or "to" in name:
                            date_edits += 1
                    except Exception:
                        continue
                if date_edits >= 2:
                    state["filter_window_open"] = True
                    logger.info("[Agent3] Filter panel confirmed open (date fields found).")
                    return state

            except Exception:
                pass
            time.sleep(0.5)

        state["error"] = (
            f"Filter panel did not appear within {timeout}s after clicking toggle."
        )
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_arrow_timeout")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"click_arrow_button failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_arrow_error")
        except Exception:
            pass

    return state
