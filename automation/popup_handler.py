"""Popup detection and dismissal for Excellon application.

Used by ALL agents to handle unexpected dialogs, confirmations,
and alerts that appear during automation.
"""

import time
from typing import Any

from pywinauto import Desktop
from loguru import logger


def wait_for_popup(timeout: int = 5) -> Any | None:
    """Poll for a popup/dialog window.

    Looks for small dialog windows that are NOT the main Excellon window.
    A popup is identified by having buttons (OK, Yes, No, Cancel) and
    a relatively small bounding rectangle.

    Args:
        timeout: Maximum seconds to wait.

    Returns:
        Popup window wrapper or None if not found within timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            all_windows = Desktop(backend="uia").windows()
            for win in all_windows:
                try:
                    title = win.window_text().strip()
                    # Skip main Excellon window
                    if "excellon" in title.lower() and "5.0" in title:
                        continue
                    # Skip empty-titled windows
                    if not title:
                        continue

                    # Check if it has typical dialog buttons
                    try:
                        buttons = win.children(control_type="Button")
                    except Exception:
                        buttons = []

                    button_texts = []
                    for btn in buttons:
                        try:
                            btn_text = btn.window_text().strip().lower()
                            button_texts.append(btn_text)
                        except Exception:
                            continue

                    dialog_buttons = {"ok", "yes", "no", "cancel", "close"}
                    if button_texts and dialog_buttons.intersection(set(button_texts)):
                        rect = win.rectangle()
                        width = rect.right - rect.left
                        height = rect.bottom - rect.top
                        # Popup windows are typically smaller than 800x600
                        if width < 800 and height < 600:
                            logger.info(
                                "Popup detected: '{}' ({}x{}) buttons={}",
                                title, width, height, button_texts,
                            )
                            return win
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("Error scanning for popups: {}", exc)

        time.sleep(0.5)

    return None


def get_popup_buttons(popup: Any) -> dict[str, Any]:
    """Extract named buttons from a popup window.

    Args:
        popup: pywinauto window wrapper for the popup.

    Returns:
        Dict mapping lowercase button names to their elements.
        Only includes keys for buttons that exist.
    """
    result: dict[str, Any] = {}
    try:
        buttons = popup.children(control_type="Button")
        for btn in buttons:
            try:
                text = btn.window_text().strip().lower()
                if text in ("yes", "ok", "no", "cancel", "close"):
                    result[text] = btn
                    logger.debug("Found button: '{}'", text)
            except Exception:
                continue
    except Exception as exc:
        logger.warning("Could not enumerate popup buttons: {}", exc)

    return result


def handle_popup_yes_ok(timeout: int = 5) -> str:
    """Wait for a popup and click Yes or OK.

    Priority: Yes button first, then OK if Yes not available.

    Args:
        timeout: Seconds to wait for popup.

    Returns:
        'yes_clicked', 'ok_clicked', or 'none_found'.
    """
    popup = wait_for_popup(timeout=timeout)
    if popup is None:
        logger.debug("No popup found within {}s.", timeout)
        return "none_found"

    buttons = get_popup_buttons(popup)

    if "yes" in buttons:
        buttons["yes"].click_input()
        logger.info("Popup '{}': clicked YES.", popup.window_text())
        return "yes_clicked"
    elif "ok" in buttons:
        buttons["ok"].click_input()
        logger.info("Popup '{}': clicked OK.", popup.window_text())
        return "ok_clicked"

    logger.warning(
        "Popup '{}' found but no Yes/OK button. Available: {}",
        popup.window_text(),
        list(buttons.keys()),
    )
    return "none_found"


def handle_popup_no(timeout: int = 5) -> str:
    """Wait for a popup and click No.

    Args:
        timeout: Seconds to wait for popup.

    Returns:
        'no_clicked' or 'none_found'.
    """
    popup = wait_for_popup(timeout=timeout)
    if popup is None:
        logger.debug("No popup found within {}s.", timeout)
        return "none_found"

    buttons = get_popup_buttons(popup)

    if "no" in buttons:
        buttons["no"].click_input()
        logger.info("Popup '{}': clicked NO.", popup.window_text())
        return "no_clicked"

    logger.warning(
        "Popup '{}' found but no No button. Available: {}",
        popup.window_text(),
        list(buttons.keys()),
    )
    return "none_found"


def dismiss_all_popups(max_iterations: int = 5) -> int:
    """Dismiss all popups by clicking Yes/OK repeatedly.

    Args:
        max_iterations: Maximum number of popups to dismiss.

    Returns:
        Count of popups dismissed.
    """
    count = 0
    for i in range(max_iterations):
        result = handle_popup_yes_ok(timeout=3)
        if result == "none_found":
            break
        count += 1
        logger.info("Popup #{} dismissed: {}", count, result)
        time.sleep(0.5)  # Brief pause between popups

    logger.info("Total popups dismissed: {}", count)
    return count
