"""Node: Select a dealer from the Dealer dropdown in the filter panel."""

import time

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.uia_retry import find_all_by_text_in_panel


def select_dealer_node(state: GlobalState) -> GlobalState:
    """Click the Dealer dropdown and select the configured dealer."""
    logger.info("[Agent3] Node: select_dealer — entering")

    dealer = state.get("dealer", "")
    if not dealer:
        logger.info("[Agent3] No dealer configured, skipping.")
        return state

    try:
        app = state["app_handle"]
        from automation.window_manager import get_main_window
        main_win = get_main_window(app)

        time.sleep(2.0)

        # 1. Find "Dealer" label in the RIGHT-SIDE filter panel
        found = find_all_by_text_in_panel(main_win, ["Dealer"], retries=5, delay=2.0)
        dealer_label = found.get("Dealer")
        if not dealer_label:
            state["error"] = "Could not find 'Dealer' label in filter panel."
            logger.error("[Agent3] {}", state["error"])
            return state

        # 2. Click the dropdown arrow (right edge of the control)
        r = dealer_label.rectangle()
        click_x = r.right - 15
        click_y = (r.top + r.bottom) // 2
        logger.info("[Agent3] Clicking Dealer dropdown at ({},{}).", click_x, click_y)
        pyautogui.click(click_x, click_y)
        time.sleep(1.5)

        # 3. Select the first item using keyboard (Home + Enter)
        pyautogui.press("home")
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(1.0)

        logger.info("[Agent3] Selected dealer '{}' via keyboard.", dealer)
        logger.info("[Agent3] Node: select_dealer — completed")

    except Exception as exc:
        state["error"] = f"select_dealer failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "select_dealer_error")
        except Exception:
            pass

    return state
