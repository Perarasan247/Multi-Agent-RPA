"""Screenshot capture utilities for debugging and visual verification."""

import time
from pathlib import Path

import cv2
import numpy as np
from PIL import ImageGrab
from loguru import logger

from config.settings import settings

_SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "logs" / "screenshots"


def capture_screen() -> np.ndarray:
    """Capture the full screen as a BGR numpy array.

    Returns:
        OpenCV-compatible BGR image.
    """
    screenshot = ImageGrab.grab()
    rgb_array = np.array(screenshot)
    bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    return bgr_array


def capture_region(x: int, y: int, w: int, h: int) -> np.ndarray:
    """Capture a specific region of the screen.

    Args:
        x: Left coordinate.
        y: Top coordinate.
        w: Width.
        h: Height.

    Returns:
        OpenCV-compatible BGR image of the region.
    """
    bbox = (x, y, x + w, y + h)
    screenshot = ImageGrab.grab(bbox=bbox)
    rgb_array = np.array(screenshot)
    bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    return bgr_array


def get_element_region(element) -> tuple[int, int, int, int]:
    """Get the screen region of a pywinauto element.

    Args:
        element: pywinauto element wrapper.

    Returns:
        Tuple of (x, y, width, height).
    """
    rect = element.rectangle()
    return (rect.left, rect.top, rect.width(), rect.height())


def save_debug_screenshot(image: np.ndarray, name: str) -> None:
    """Save a debug screenshot if LOG_LEVEL is DEBUG.

    Args:
        image: BGR numpy array.
        name: Descriptive name for the file.
    """
    if settings.log_level.upper() != "DEBUG":
        return

    _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filepath = _SCREENSHOT_DIR / f"{name}_{timestamp}.png"
    cv2.imwrite(str(filepath), image)
    logger.debug("Debug screenshot saved: {}", filepath)
