"""Search bar interaction for Excellon navigation."""

import time
from typing import Any

from pywinauto import Application
from loguru import logger

from automation.keyboard_mouse import clear_field, type_text_slow
from automation.ui_tree_reader import walk_tree_items, check_is_selected


class SearchBarNotFoundError(Exception):
    """Raised when the search bar cannot be located."""
    pass


def find_search_bar(app: Application) -> Any:
    """Locate the search bar in the application.

    Tries multiple strategies:
    1. AutomationId containing 'search'
    2. Placeholder text containing 'Type keywords'
    3. First Edit control in the top-left region

    Args:
        app: pywinauto Application handle.

    Returns:
        The search bar element.

    Raises:
        SearchBarNotFoundError: If no search bar is found.
    """
    main_win = app.top_window()

    # Strategy 1: AutomationId-based
    try:
        edits = main_win.descendants(control_type="Edit")
        for edit in edits:
            try:
                auto_id = (edit.element_info.automation_id or "").lower()
                if "search" in auto_id:
                    logger.debug("Found search bar by AutomationId: '{}'", auto_id)
                    return edit
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: Placeholder text
    try:
        edits = main_win.descendants(control_type="Edit")
        for edit in edits:
            try:
                text = edit.window_text().lower()
                name = (edit.element_info.name or "").lower()
                if "type keyword" in text or "search" in text or "type keyword" in name or "search" in name:
                    logger.debug("Found search bar by placeholder text.")
                    return edit
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 3: First Edit in top-left quadrant
    try:
        win_rect = main_win.rectangle()
        mid_x = (win_rect.left + win_rect.right) // 2
        mid_y = (win_rect.top + win_rect.bottom) // 2
        edits = main_win.descendants(control_type="Edit")
        for edit in edits:
            try:
                rect = edit.rectangle()
                if rect.left < mid_x and rect.top < mid_y:
                    logger.debug("Found search bar in top-left quadrant.")
                    return edit
            except Exception:
                continue
    except Exception:
        pass

    raise SearchBarNotFoundError(
        "Could not locate search bar in the application window."
    )


def clear_and_type_search(search_bar: Any, term: str) -> None:
    """Clear the search bar and type a search term.

    Args:
        search_bar: The search bar element.
        term: Search term to type.
    """
    # type_text_slow handles clearing internally; don't clear twice
    type_text_slow(search_bar, term, delay=0.05)
    logger.info("Search typed: '{}'", term)


def wait_for_results(panel: Any, timeout: int = 10) -> bool:
    """Wait for search results to appear in the tree panel.

    Polls until at least one TreeItem is selected or the count
    of visible items increases.

    Args:
        panel: The tree/panel to monitor.
        timeout: Maximum seconds to wait.

    Returns:
        True when results appear, False on timeout.
    """
    # Get baseline count
    try:
        baseline_items = walk_tree_items(panel)
        baseline_count = len(baseline_items)
    except Exception:
        baseline_count = 0

    start = time.time()
    while time.time() - start < timeout:
        try:
            items = walk_tree_items(panel)
            # Check for any selected item
            for item in items:
                if item["is_selected"]:
                    logger.info("Search results appeared: selected item found.")
                    return True
            # Check for increased item count
            if len(items) > baseline_count:
                logger.info(
                    "Search results appeared: item count {} → {}.",
                    baseline_count, len(items),
                )
                return True
        except Exception:
            pass

        time.sleep(0.5)

    logger.warning("Search results did not appear within {}s.", timeout)
    return False
