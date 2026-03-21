"""Node: Type the report name into the search bar."""

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import focus_window as wm_focus_window
from automation.search_handler import find_search_bar, clear_and_type_search
from automation.screenshot import capture_screen, save_debug_screenshot


def type_search_node(state: GlobalState) -> GlobalState:
    """Type the report name into the application search bar.

    Ensures focus first, then finds the search bar and types
    character by character with 50ms delay.
    """
    logger.info("[Agent2] Node: type_search — entering")
    try:
        app = state["app_handle"]

        # Ensure focus
        try:
            wm_focus_window(app, settings.app_window_title)
        except Exception:
            logger.warning("Could not re-verify focus before typing search.")

        # Find and use search bar
        search_bar = find_search_bar(app)
        report_name = state["report_name"]

        clear_and_type_search(search_bar, report_name)

        # Verify search bar text
        try:
            actual = search_bar.get_value() or search_bar.window_text() or ""
            if actual.strip() == report_name.strip():
                logger.info("Search bar text verified: '{}'", report_name)
            else:
                logger.warning(
                    "Search bar text mismatch: expected='{}', actual='{}'",
                    report_name, actual,
                )
        except Exception:
            logger.debug("Could not verify search bar text.")

        state["search_typed"] = True
        logger.info("[Agent2] Node: type_search — completed")

    except Exception as exc:
        state["error"] = f"type_search failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "type_search_error")
        except Exception:
            pass

    return state
