"""Search bar interaction for Excellon navigation."""

import time
from typing import Any

import pyautogui
import pygetwindow as gw
from pywinauto import Application
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_element_info import UIAElementInfo
from loguru import logger

from automation.keyboard_mouse import type_text_slow
from automation.ui_tree_reader import walk_tree_items, check_is_selected
from automation.window_manager import _is_excellon_window
from config.settings import settings

pyautogui.FAILSAFE = False


class SearchBarNotFoundError(Exception):
    """Raised when the search bar cannot be located."""
    pass


def _get_excellon_uia_wrapper():
    """Get a UIA wrapper for the main Excellon window by HWND (fast)."""
    for w in gw.getAllWindows():
        if w.title and _is_excellon_window(w.title, settings.app_window_title):
            try:
                return UIAWrapper(UIAElementInfo(w._hWnd))
            except Exception:
                continue
    return None


def find_search_bar(app: Application = None) -> Any:
    """Locate the search bar in the application.

    Uses pygetwindow + UIAWrapper on the HWND to avoid slow app.top_window().

    Tries multiple strategies:
    1. Edit with name/text containing 'keyword' or 'search'
    2. AutomationId containing 'search'
    3. First Edit in top-left quadrant

    Returns:
        The search bar element.

    Raises:
        SearchBarNotFoundError: If no search bar is found.
    """
    wrapper = _get_excellon_uia_wrapper()
    if wrapper is None:
        raise SearchBarNotFoundError("Cannot find Excellon window.")

    edits = []
    for d in wrapper.descendants():
        try:
            if d.element_info.control_type == "Edit":
                edits.append(d)
        except Exception:
            continue

    # Strategy 1: Name/text containing 'keyword' or 'search'
    for edit in edits:
        try:
            text = (edit.window_text() or "").lower()
            name = (edit.element_info.name or "").lower()
            if "keyword" in text or "keyword" in name or "search" in text or "search" in name:
                logger.debug("Found search bar by name/text: '{}'", name or text)
                return edit
        except Exception:
            continue

    # Strategy 2: AutomationId
    for edit in edits:
        try:
            auto_id = (edit.element_info.automation_id or "").lower()
            if "search" in auto_id:
                logger.debug("Found search bar by AutomationId: '{}'", auto_id)
                return edit
        except Exception:
            continue

    # Strategy 3: First Edit in top-left quadrant
    try:
        win_rect = wrapper.rectangle()
        mid_x = (win_rect.left + win_rect.right) // 2
        mid_y = (win_rect.top + win_rect.bottom) // 2
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
    """Clear the search bar and type a search term."""
    type_text_slow(search_bar, term, delay=0.05)
    logger.info("Search typed: '{}'", term)


def wait_for_results(panel: Any, timeout: int = 10) -> bool:
    """Wait for search results to appear in the tree panel."""
    try:
        baseline_items = walk_tree_items(panel)
        baseline_count = len(baseline_items)
    except Exception:
        baseline_count = 0

    start = time.time()
    while time.time() - start < timeout:
        try:
            items = walk_tree_items(panel)
            for item in items:
                if item["is_selected"]:
                    logger.info("Search results appeared: selected item found.")
                    return True
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
