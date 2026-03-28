"""Retry wrapper for UIA descendants() calls.

UIA/COM can intermittently fail to enumerate controls in .NET apps.
This module retries the descendants() call multiple times with delays.
"""

import time
from typing import Any
from loguru import logger


def find_descendant_by_text(window: Any, text: str, retries: int = 5,
                            delay: float = 2.0) -> Any | None:
    """Find a descendant control by exact text match with retries.

    Args:
        window: pywinauto window wrapper.
        text: Exact text to match.
        retries: Number of attempts.
        delay: Seconds between retries.

    Returns:
        The matching control, or None.
    """
    for attempt in range(retries):
        try:
            for d in window.descendants():
                try:
                    if (d.window_text() or "").strip() == text:
                        return d
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("descendants() failed (attempt {}): {}", attempt + 1, exc)

        if attempt < retries - 1:
            time.sleep(delay)

    return None


def find_descendant_by_auto_id(window: Any, auto_id: str, retries: int = 5,
                                delay: float = 2.0) -> Any | None:
    """Find a descendant control by automation ID with retries."""
    for attempt in range(retries):
        try:
            for d in window.descendants():
                try:
                    if (d.element_info.automation_id or "") == auto_id:
                        return d
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("descendants() failed (attempt {}): {}", attempt + 1, exc)

        if attempt < retries - 1:
            time.sleep(delay)

    return None


def find_all_by_text_in_panel(window: Any, texts: list[str], retries: int = 5,
                               delay: float = 2.0) -> dict[str, Any]:
    """Find multiple controls by text in the right-side filter panel.

    Returns a dict mapping text -> control for all found matches.
    Retries until at least one is found or retries exhausted.
    """
    win_rect = window.rectangle()
    right_threshold = win_rect.right - 600

    for attempt in range(retries):
        found = {}
        try:
            for d in window.descendants():
                try:
                    txt = (d.window_text() or "").strip()
                    if txt in texts:
                        r = d.rectangle()
                        if r.left > right_threshold:
                            found[txt] = d
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("descendants() failed (attempt {}): {}", attempt + 1, exc)

        if found:
            return found

        if attempt < retries - 1:
            time.sleep(delay)

    return {}
