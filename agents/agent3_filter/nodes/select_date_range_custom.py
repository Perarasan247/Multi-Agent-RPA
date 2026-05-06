"""Node: Select 'Custom' from the Date Range dropdown.

Selection strategy (two tiers):
  Tier 1  pywinauto native select("Custom") on the ComboBox control — works
          regardless of item position in the dropdown list.
  Tier 2  Click dropdown open → Home → "c" → Enter — WinForms ListBoxes jump
          to the first item starting with the typed character. "Custom" is the
          only option beginning with 'C' across all known report dropdowns.
"""

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.uia_retry import find_all_by_text_in_panel


# ── Helpers ───────────────────────────────────────────────────────────────────


def _find_combo_and_coords(main_win, found: dict):
    """Return (combo_ctrl, click_x, click_y) for the Date Range ComboBox."""
    date_ctrl = found.get("Date Range")
    if date_ctrl is not None:
        r = date_ctrl.rectangle()
        return date_ctrl, r.right - 15, (r.top + r.bottom) // 2

    for key in ["Month To Date", "Week To Date", "Year To Date",
                "Previous Month", "Custom", "Previous Year",
                "Inception To Date", "As On Date", "Single Day", "Single Week"]:
        if key in found:
            ctrl = found[key]
            r = ctrl.rectangle()
            return ctrl, r.right - 15, (r.top + r.bottom) // 2

    return None, None, None


def _try_native_select(ctrl) -> bool:
    """Tier 1: pywinauto native ComboBox.select('Custom')."""
    try:
        ctrl.select("Custom")
        logger.info("[Agent3] Selected 'Custom' via native ComboBox.select().")
        return True
    except Exception:
        return False


def _open_and_keyboard_select(click_x: int, click_y: int) -> None:
    """Tier 2: Open dropdown then jump to 'Custom' by first-letter navigation."""
    pyautogui.click(click_x, click_y)
    time.sleep(0.8)
    # In WinForms ComboBox/ListBox, typing a character jumps to the first item
    # starting with that character. "Custom" is the only item starting with 'C'.
    pyautogui.press("home")
    time.sleep(0.2)
    pyautogui.press("c")
    time.sleep(0.3)
    pyautogui.press("enter")
    logger.info("[Agent3] Selected 'Custom' via keyboard (Home → 'c' → Enter).")


# ── Main node ─────────────────────────────────────────────────────────────────


def select_date_range_custom_node(state: GlobalState) -> GlobalState:
    """Open the Date Range dropdown and select 'Custom'."""
    logger.info("[Agent3] Node: select_date_range_custom — entering")
    try:
        app = state["app_handle"]
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        time.sleep(2.0)

        # Find the Date Range control in the filter panel
        search_texts = [
            "Date Range", "Month To Date", "Week To Date", "Year To Date",
            "Custom", "Previous Month", "Previous Year", "Inception To Date",
            "As On Date", "Single Day", "Single Week",
        ]
        found = find_all_by_text_in_panel(main_win, search_texts, retries=5, delay=2.0)

        if not found:
            state["error"] = "Date Range control not found after retries."
            logger.error("[Agent3] {}", state["error"])
            return state

        logger.info("[Agent3] Found filter panel controls: {}", list(found.keys()))

        combo_ctrl, click_x, click_y = _find_combo_and_coords(main_win, found)

        if combo_ctrl is None:
            state["error"] = "Could not identify Date Range ComboBox control."
            logger.error("[Agent3] {}", state["error"])
            return state

        # Tier 1: native select
        if not _try_native_select(combo_ctrl):
            # Tier 2: click open + keyboard first-letter navigation
            _open_and_keyboard_select(click_x, click_y)

        time.sleep(1.0)

        # Press TAB to unlock the From / To date fields
        logger.info("[Agent3] Pressing TAB to unlock date fields.")
        pyautogui.press("tab")
        time.sleep(0.5)

        state["date_range_set"] = True
        logger.info("[Agent3] Node: select_date_range_custom — completed")

    except Exception as exc:
        state["error"] = f"select_date_range_custom failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "select_date_range_error")
        except Exception:
            pass

    return state
