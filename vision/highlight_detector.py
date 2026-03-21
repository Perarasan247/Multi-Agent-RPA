"""OpenCV-based blue highlight detection for tree item selection verification."""

import cv2
import numpy as np
from loguru import logger

# HSV range for blue selection highlight in Windows UIA trees
BLUE_HSV_LOWER = np.array([100, 100, 100])
BLUE_HSV_UPPER = np.array([130, 255, 255])


def detect_blue_highlights(image: np.ndarray) -> list[dict]:
    """Detect blue highlighted regions in an image.

    Converts the image to HSV color space and applies a mask
    for the blue highlight range typical of Windows selection bars.

    Args:
        image: BGR numpy array (from OpenCV or screenshot).

    Returns:
        List of dicts with keys: x, y, w, h, area, center_y.
        Filtered to exclude noise (area < 100).
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BLUE_HSV_LOWER, BLUE_HSV_UPPER)

    # Morphological cleanup
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    highlights: list[dict] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 100:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        center_y = y + h // 2

        highlights.append({
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
            "area": float(area),
            "center_y": int(center_y),
        })

    logger.debug("Detected {} blue highlight regions.", len(highlights))
    return highlights


def find_full_width_highlight(
    highlights: list[dict],
    panel_width: int,
    target_center_y: int,
    tolerance_y: int = 10,
) -> dict | None:
    """Find a full-width highlight near a target Y position.

    Looks for a highlight that spans at least 85% of the panel width
    and is vertically close to the expected item position.

    Args:
        highlights: List of highlight dicts from detect_blue_highlights.
        panel_width: Width of the navigation panel in pixels.
        target_center_y: Expected Y center of the selected item.
        tolerance_y: Maximum Y deviation allowed.

    Returns:
        Matching highlight dict, or None if not found.
    """
    min_width = int(panel_width * 0.85)

    candidates = [h for h in highlights if h["w"] >= min_width]
    logger.debug(
        "Full-width candidates (>= {}px): {} out of {} highlights.",
        min_width, len(candidates), len(highlights),
    )

    for highlight in candidates:
        y_diff = abs(highlight["center_y"] - target_center_y)
        if y_diff <= tolerance_y:
            logger.info(
                "Full-width highlight match at y={} (target={}, diff={}).",
                highlight["center_y"], target_center_y, y_diff,
            )
            return highlight

    logger.debug(
        "No full-width highlight found near y={} (tolerance={}px).",
        target_center_y, tolerance_y,
    )
    return None


def find_yellow_highlight_coords(
    screenshot: np.ndarray,
    panel_left: int,
    panel_top: int,
    panel_width: int,
    panel_height: int,
) -> tuple[int, int] | None:
    """Find the center screen coordinates of a yellow-highlighted tree item.

    Excellon's search highlights matching text in yellow. This detects the
    deepest (lowest Y) yellow region in the left panel — that is the leaf
    report item, not a folder.

    Args:
        screenshot: Full-screen BGR numpy array.
        panel_left: Left edge of the panel in screen pixels.
        panel_top: Top edge of the panel in screen pixels.
        panel_width: Width of the panel in pixels.
        panel_height: Height of the panel in pixels.

    Returns:
        (screen_x, screen_y) center of the deepest yellow highlight, or None.
    """
    # Crop to the left panel — clamp to screenshot bounds
    img_h, img_w = screenshot.shape[:2]
    y1 = max(0, panel_top)
    y2 = min(img_h, panel_top + panel_height)
    x1 = max(0, panel_left)
    x2 = min(img_w, panel_left + panel_width)

    if y2 <= y1 or x2 <= x1:
        logger.warning("find_yellow_highlight_coords: crop region is empty ({},{},{},{}).", x1, y1, x2, y2)
        return None

    crop = screenshot[y1:y2, x1:x2]

    if crop.size == 0:
        logger.warning("find_yellow_highlight_coords: crop array is empty.")
        return None

    crop_h, crop_w = crop.shape[:2]

    # Exclude the bottom 60px of the crop to avoid taskbar / status bar noise
    safe_crop = crop[: max(crop_h - 60, crop_h // 2), :]
    if safe_crop.size == 0:
        safe_crop = crop

    hsv = cv2.cvtColor(safe_crop, cv2.COLOR_BGR2HSV)
    kernel = np.ones((3, 3), np.uint8)

    # Highlighted tree items must be at least this wide (relative to crop width)
    # and have a meaningful area — filters out scrollbars, icons, taskbar noise.
    min_width = max(20, crop_w // 5)   # at least 20% of panel width
    min_area  = 200                     # at least ~15×13 px

    # Color ranges ordered from most-specific (orange/yellow) to broadest.
    # "any_sat" is omitted — far too noisy; use Gemini as the broader fallback.
    color_ranges = [
        ("orange", np.array([5,  100, 100]), np.array([25, 255, 255])),
        ("yellow", np.array([20,  80,  80]), np.array([45, 255, 255])),
        ("amber",  np.array([10,  60, 120]), np.array([30, 255, 255])),
        ("blue",   np.array([100,120, 120]), np.array([130,255, 255])),
    ]

    all_valid = []
    for color_name, lo, hi in color_ranges:
        mask = cv2.inRange(hsv, lo, hi)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw < min_width:
                continue
            all_valid.append((bx, by, bw, bh, area, color_name))

    if not all_valid:
        logger.debug("find_yellow_highlight_coords: no valid highlight regions found.")
        return None

    # Among qualifying regions, pick the lowest (deepest tree item = leaf, not folder)
    bx, by, bw, bh, area, color_name = max(all_valid, key=lambda v: v[1])
    cx = x1 + bx + bw // 2
    cy = y1 + by + bh // 2

    logger.info(
        "Highlight ({}) found at crop ({},{} {}x{} area={:.0f}) → screen ({},{}).",
        color_name, bx, by, bw, bh, area, cx, cy,
    )
    return cx, cy


def find_all_highlight_coords(
    screenshot: np.ndarray,
    panel_left: int,
    panel_top: int,
    panel_width: int,
    panel_height: int,
) -> list[tuple[int, int]]:
    """Return screen coords of ALL distinct highlighted regions in the panel.

    Same detection logic as find_yellow_highlight_coords but returns every
    qualifying region, not just the bottom-most one. Used when multiple
    results appear and further disambiguation (e.g. Gemini) is needed.

    Returns:
        List of (screen_x, screen_y) tuples, ordered top-to-bottom.
    """
    img_h, img_w = screenshot.shape[:2]
    y1 = max(0, panel_top)
    y2 = min(img_h, panel_top + panel_height)
    x1 = max(0, panel_left)
    x2 = min(img_w, panel_left + panel_width)

    if y2 <= y1 or x2 <= x1:
        return []

    crop = screenshot[y1:y2, x1:x2]
    if crop.size == 0:
        return []

    crop_h, crop_w = crop.shape[:2]
    safe_crop = crop[: max(crop_h - 60, crop_h // 2), :]
    if safe_crop.size == 0:
        safe_crop = crop

    hsv = cv2.cvtColor(safe_crop, cv2.COLOR_BGR2HSV)
    kernel = np.ones((3, 3), np.uint8)

    min_width = max(20, crop_w // 5)
    min_area = 200

    color_ranges = [
        ("orange", np.array([5,  100, 100]), np.array([25, 255, 255])),
        ("yellow", np.array([20,  80,  80]), np.array([45, 255, 255])),
        ("amber",  np.array([10,  60, 120]), np.array([30, 255, 255])),
        ("blue",   np.array([100,120, 120]), np.array([130,255, 255])),
    ]

    seen_y: list[int] = []
    results: list[tuple[int, int, float]] = []  # (screen_x, screen_y, area)

    for color_name, lo, hi in color_ranges:
        mask = cv2.inRange(hsv, lo, hi)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            bx, by, bw, bh = cv2.boundingRect(cnt)
            if bw < min_width:
                continue
            cy = y1 + by + bh // 2
            cx = x1 + bx + bw // 2
            # Deduplicate: skip if within 15px of an already-found region
            if any(abs(cy - ey) < 15 for ey in seen_y):
                continue
            seen_y.append(cy)
            results.append((cx, cy, area))

    results.sort(key=lambda r: r[1])  # top-to-bottom order
    logger.debug("find_all_highlight_coords: {} distinct regions found.", len(results))
    return results
