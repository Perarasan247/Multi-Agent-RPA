"""Keyboard and mouse interaction utilities."""

import time

import pyautogui
from loguru import logger


def type_text_slow(element, text: str, delay: float = 0.05) -> None:
    """Type text into an element using a single pywinauto type_keys call.

    Typing char-by-char causes Excellon's live-search to steal focus
    between keystrokes. Sending the full string in one type_keys call
    routes all input directly to the element before the UI can react.

    Args:
        element: pywinauto element to type into.
        text: The text string to type.
        delay: Seconds between each keystroke (pause parameter).
    """
    # Click to focus, then clear via Ctrl+A + Delete
    element.click_input()
    time.sleep(0.1)
    element.type_keys("^a{DELETE}", with_spaces=True)
    time.sleep(0.2)

    # Type the full string in one call so focus cannot be stolen mid-type
    element.type_keys(text, with_spaces=True, pause=delay)
    time.sleep(0.2)

    # Verify typed text matches
    try:
        actual = element.get_value()
        if actual is None:
            actual = element.window_text()
        if actual and actual.strip() != text.strip():
            logger.warning(
                "Text verification mismatch: expected='{}', actual='{}'",
                text, actual,
            )
    except Exception:
        logger.debug("Could not verify typed text (element may not support get_value).")

    logger.debug("Typed text: '{}' ({} chars)", text[:30] + "..." if len(text) > 30 else text, len(text))


def clear_field(element) -> None:
    """Clear a text field by selecting all content and deleting it.

    Args:
        element: pywinauto element to clear.
    """
    try:
        element.click_input()
        time.sleep(0.1)
        # Triple-click to select all
        pyautogui.click(clicks=3)
        time.sleep(0.1)
        pyautogui.press("delete")
        time.sleep(0.1)

        # Fallback: Ctrl+A then Delete
        try:
            remaining = element.get_value() or element.window_text() or ""
            if remaining.strip():
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.press("delete")
                time.sleep(0.1)
        except Exception:
            pass

        logger.debug("Field cleared.")
    except Exception as exc:
        logger.warning("Error clearing field: {}", exc)


def press_key(key: str) -> None:
    """Press a single key.

    Args:
        key: Key name (e.g., 'tab', 'enter', 'escape').
    """
    pyautogui.press(key)
    logger.debug("Key pressed: {}", key)


def press_hotkey(*keys: str) -> None:
    """Press a key combination.

    Args:
        *keys: Key names to press simultaneously.
    """
    pyautogui.hotkey(*keys)
    logger.debug("Hotkey pressed: {}", " + ".join(keys))


def click_element(element) -> None:
    """Click an element using click_input.

    Args:
        element: pywinauto element to click.
    """
    element.click_input()
    text = ""
    try:
        text = element.window_text()
    except Exception:
        pass
    logger.debug("Clicked element: '{}'", text)


def double_click_element(element) -> None:
    """Double-click an element using double_click_input.

    Args:
        element: pywinauto element to double-click.
    """
    element.double_click_input()
    text = ""
    try:
        text = element.window_text()
    except Exception:
        pass
    logger.debug("Double-clicked element: '{}'", text)


def scroll_element_into_view(element) -> None:
    """Scroll an element into the visible area.

    Args:
        element: pywinauto element to scroll to.
    """
    try:
        # Try UIA ScrollIntoView first
        iface = element.iface_scroll_item
        if iface:
            iface.ScrollIntoView()
            logger.debug("Scrolled element into view via ScrollItemPattern.")
            return
    except Exception:
        pass

    try:
        # Fallback: ensure_visible for tree items
        element.ensure_visible()
        logger.debug("Scrolled element into view via ensure_visible.")
        return
    except Exception:
        pass

    # Last resort: click to focus, which may auto-scroll
    try:
        element.set_focus()
        logger.debug("Set focus on element to scroll it into view.")
    except Exception as exc:
        logger.warning("Could not scroll element into view: {}", exc)
