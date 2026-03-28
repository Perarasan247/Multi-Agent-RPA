"""Find text on screen using OpenCV template matching with rendered text.

Since some Excellon reports don't expose controls via UIA/win32,
this module renders expected text labels as images and uses OpenCV
matchTemplate to find them on screen.
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from loguru import logger


def _render_text_template(text: str, font_size: int = 14,
                          font_name: str = "arial") -> np.ndarray:
    """Render text as a grayscale image for template matching.

    Args:
        text: The text to render.
        font_size: Font size in pixels.
        font_name: Font family name.

    Returns:
        Grayscale numpy array of the rendered text.
    """
    try:
        font = ImageFont.truetype(f"{font_name}.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    # Measure text size
    dummy_img = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0] + 4
    th = bbox[3] - bbox[1] + 4

    # Render text on white background with black text
    img = Image.new("RGB", (tw, th), "white")
    draw = ImageDraw.Draw(img)
    draw.text((2, 2 - bbox[1]), text, fill="black", font=font)

    # Convert to grayscale numpy array
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return gray


def find_text_on_screen(screen_bgr: np.ndarray, text: str,
                        region: tuple[int, int, int, int] | None = None,
                        threshold: float = 0.7,
                        font_sizes: list[int] | None = None) -> tuple[int, int] | None:
    """Find text on screen using template matching.

    Tries multiple font sizes and returns the best match.

    Args:
        screen_bgr: Full screen capture (BGR).
        text: Text to find.
        region: Optional (x, y, w, h) to search within.
        threshold: Minimum confidence (0-1).
        font_sizes: List of font sizes to try.

    Returns:
        (click_x, click_y) center of the found text, or None.
    """
    if font_sizes is None:
        font_sizes = [12, 13, 14, 11, 15, 10, 16]

    # Crop to region if specified
    if region is not None:
        rx, ry, rw, rh = region
        search_img = screen_bgr[ry:ry + rh, rx:rx + rw]
        offset_x, offset_y = rx, ry
    else:
        search_img = screen_bgr
        offset_x, offset_y = 0, 0

    gray_screen = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)

    best_val = 0.0
    best_loc = None
    best_size = None
    best_tw = 0
    best_th = 0

    for fs in font_sizes:
        template = _render_text_template(text, font_size=fs)
        th, tw = template.shape[:2]

        # Skip if template is larger than search area
        if tw > gray_screen.shape[1] or th > gray_screen.shape[0]:
            continue

        result = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_size = fs
            best_tw = tw
            best_th = th

    if best_val >= threshold and best_loc is not None:
        cx = offset_x + best_loc[0] + best_tw // 2
        cy = offset_y + best_loc[1] + best_th // 2
        logger.debug("Found '{}' at ({},{}) conf={:.2f} font_size={}",
                      text, cx, cy, best_val, best_size)
        return (cx, cy)

    logger.debug("Text '{}' not found (best conf={:.2f})", text, best_val)
    return None


def find_text_left_edge(screen_bgr: np.ndarray, text: str,
                        region: tuple[int, int, int, int] | None = None,
                        threshold: float = 0.7,
                        font_sizes: list[int] | None = None) -> tuple[int, int] | None:
    """Find text on screen and return the LEFT edge coordinate.

    Useful for clicking checkboxes where the box is to the left of the label.

    Returns:
        (left_x, center_y) of the found text, or None.
    """
    if font_sizes is None:
        font_sizes = [12, 13, 14, 11, 15, 10, 16]

    if region is not None:
        rx, ry, rw, rh = region
        search_img = screen_bgr[ry:ry + rh, rx:rx + rw]
        offset_x, offset_y = rx, ry
    else:
        search_img = screen_bgr
        offset_x, offset_y = 0, 0

    gray_screen = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)

    best_val = 0.0
    best_loc = None
    best_th = 0

    for fs in font_sizes:
        template = _render_text_template(text, font_size=fs)
        th, tw = template.shape[:2]
        if tw > gray_screen.shape[1] or th > gray_screen.shape[0]:
            continue
        result = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_th = th

    if best_val >= threshold and best_loc is not None:
        lx = offset_x + best_loc[0]
        cy = offset_y + best_loc[1] + best_th // 2
        logger.debug("Found '{}' left edge at ({},{}) conf={:.2f}", text, lx, cy, best_val)
        return (lx, cy)

    return None
