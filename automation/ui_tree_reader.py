"""UI tree traversal for the left navigation panel."""

from typing import Any

from pywinauto import Application
from loguru import logger


def get_left_panel(app: Application) -> Any:
    """Find the left navigation/tree panel in the application.

    Tries AutomationId-based lookup first, then falls back to
    positional detection (leftmost panel with tree items).

    Args:
        app: pywinauto Application handle.

    Returns:
        Panel wrapper element.

    Raises:
        RuntimeError: If the left panel cannot be found.
    """
    from automation.window_manager import get_main_window
    main_win = get_main_window(app)

    # Strategy 1: Look for Tree or TreeView control
    try:
        trees = main_win.descendants(control_type="Tree")
        if trees:
            logger.debug("Found tree control directly.")
            return trees[0]
    except Exception:
        pass

    # Strategy 2: Look for Pane with TreeItem children
    try:
        panes = main_win.descendants(control_type="Pane")
        for pane in panes:
            try:
                tree_items = pane.descendants(control_type="TreeItem")
                if tree_items:
                    rect = pane.rectangle()
                    screen_mid = main_win.rectangle().mid_point()[0]
                    if rect.left < screen_mid:
                        logger.debug(
                            "Found left panel (Pane) at x={} with {} tree items.",
                            rect.left, len(tree_items),
                        )
                        return pane
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 3: Look for any container with "navigation" or "menu" in name
    try:
        for child in main_win.children():
            try:
                auto_id = child.element_info.automation_id or ""
                name = child.window_text().lower()
                if "nav" in auto_id.lower() or "menu" in name or "tree" in auto_id.lower():
                    logger.debug("Found panel by automation ID: '{}'", auto_id)
                    return child
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 4: Look for List control (some apps use ListView for search results)
    try:
        lists = main_win.descendants(control_type="List")
        if lists:
            logger.debug("Found List control as fallback panel.")
            return lists[0]
    except Exception:
        pass

    # Strategy 5: Any Pane with ListItem children
    try:
        panes = main_win.descendants(control_type="Pane")
        for pane in panes:
            try:
                list_items = pane.descendants(control_type="ListItem")
                if list_items:
                    logger.debug("Found Pane with ListItem children as panel.")
                    return pane
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: return the main window so callers can search all descendants
    logger.warning("Left panel not found by any strategy — falling back to main window.")
    return main_win


def walk_tree_items(panel: Any) -> list[dict]:
    """Collect all TreeItem/ListItem controls in a panel via descendants().

    Uses descendants() rather than recursive children() for reliability
    with custom WinForms/DevExpress controls. Reconstructs depth and
    parent_texts by walking each item's parent chain.

    Args:
        panel: The panel or tree wrapper to walk.

    Returns:
        List of dicts with keys: text, element, rect, depth,
        is_selected, parent_texts.
    """
    results: list[dict] = []

    # Container types to skip when doing broad fallback search
    _CONTAINER_TYPES = {
        "Window", "Pane", "Group", "MenuBar", "ToolBar", "Menu",
        "StatusBar", "TitleBar", "ScrollBar", "Separator", "Edit",
        "Button", "ComboBox", "Tab", "TabItem", "Header", "HeaderItem",
        "Image", "Thumb", "ScrollBar", "ProgressBar", "Slider",
    }

    raw_items: list[Any] = []

    # Pass 1: standard tree/list item types
    for ctrl_type in ("TreeItem", "ListItem", "DataItem"):
        try:
            found = panel.descendants(control_type=ctrl_type)
            if found:
                raw_items.extend(found)
                logger.debug("Found {} items via descendants(control_type='{}').", len(found), ctrl_type)
        except Exception:
            pass

    # Pass 2: if nothing found, try Custom controls (DevExpress / Telerik trees)
    if not raw_items:
        try:
            found = panel.descendants(control_type="Custom")
            if found:
                raw_items.extend(found)
                logger.debug("Found {} Custom controls as fallback.", len(found))
        except Exception:
            pass

    # Pass 3: nuclear fallback — all descendants with non-empty text, skip containers
    if not raw_items:
        logger.debug("Standard control types found nothing — scanning all descendants.")
        try:
            for elem in panel.descendants():
                try:
                    ctrl_type = elem.element_info.control_type
                    if ctrl_type in _CONTAINER_TYPES:
                        continue
                    text = elem.window_text().strip()
                    if text:
                        raw_items.append(elem)
                except Exception:
                    continue
        except Exception:
            pass
        logger.debug("Broad scan found {} candidate elements.", len(raw_items))

    if not raw_items:
        logger.warning("walk_tree_items: no items found by any strategy.")
        return results

    for item in raw_items:
        text = ""
        try:
            text = item.window_text().strip()
        except Exception:
            pass

        rect = None
        try:
            rect = item.rectangle()
        except Exception:
            pass

        # Build parent_texts and depth by walking up the element's parent chain
        parent_texts: list[str] = []
        depth = 0
        try:
            ancestor = item.parent()
            while ancestor is not None:
                try:
                    a_type = ancestor.element_info.control_type
                except Exception:
                    break
                if a_type in ("TreeItem", "ListItem"):
                    a_text = ""
                    try:
                        a_text = ancestor.window_text().strip()
                    except Exception:
                        pass
                    parent_texts.insert(0, a_text)
                    depth += 1
                elif a_type in ("Tree", "List", "Pane", "Window"):
                    break
                try:
                    ancestor = ancestor.parent()
                except Exception:
                    break
        except Exception:
            pass

        results.append({
            "text": text,
            "element": item,
            "rect": rect,
            "depth": depth,
            "is_selected": check_is_selected(item),
            "parent_texts": parent_texts,
        })

    logger.debug("Walked tree: {} items found.", len(results))
    return results


def check_is_selected(element: Any) -> bool:
    """Check if a tree item is currently selected.

    Tries SelectionItemPattern first, then falls back to
    LegacyIAccessible state flags.

    Args:
        element: pywinauto element to check.

    Returns:
        True if the element appears selected.
    """
    # Strategy 1: SelectionItemPattern
    try:
        iface = element.iface_selection_item
        if iface and iface.IsSelected:
            return True
    except Exception:
        pass

    # Strategy 2: LegacyIAccessible state
    try:
        legacy = element.legacy_properties()
        state = legacy.get("State", 0)
        # STATE_SYSTEM_SELECTED = 0x2, STATE_SYSTEM_FOCUSED = 0x4
        if state & 0x2 or state & 0x4:
            return True
    except Exception:
        pass

    # Strategy 3: Check element info
    try:
        if element.is_selected():
            return True
    except Exception:
        pass

    return False


def build_tree_path(item: dict) -> list[str]:
    """Build the full path from root to a tree item.

    Args:
        item: Dict from walk_tree_items with 'parent_texts' and 'text'.

    Returns:
        List of strings representing the path from root to item.
    """
    return item["parent_texts"] + [item["text"]]


def find_items_by_text(panel: Any, search_text: str) -> list[dict]:
    """Find tree items whose text contains the search string.

    Args:
        panel: The tree/panel to search.
        search_text: Text to search for (case-insensitive).

    Returns:
        List of matching item dicts.
    """
    all_items = walk_tree_items(panel)
    matches = [
        item for item in all_items
        if search_text.lower() in item["text"].lower()
    ]
    logger.debug(
        "Search '{}': {} matches out of {} items.",
        search_text, len(matches), len(all_items),
    )
    return matches
