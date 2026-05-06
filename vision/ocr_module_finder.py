"""OCR-based module locator using RapidOCR (ONNX runtime).

Used when UIA-based matching fails for the left-menu click step.
A common case is UIA returning the wrong control because the module
name appears as a child text fragment inside another menu item
(e.g. 'Service' inside 'Authorized Service Dealer'), or because the
descendants tree has stale data.

RapidOCR is fully self-contained — no Tesseract binary required.
"""

from typing import List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger


# Lazy-init RapidOCR engine — first call downloads / loads the ONNX
# models (~50 MB). Cached for subsequent calls.
_engine = None


def _get_engine():
    """Return a RapidOCR engine, or None if the SDK isn't available."""
    global _engine
    if _engine is not None:
        return _engine
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        logger.warning(
            "[OCR] rapidocr-onnxruntime not installed — skipping OCR fallback."
        )
        return None
    try:
        _engine = RapidOCR()
        logger.info("[OCR] RapidOCR engine initialized.")
    except Exception as exc:
        logger.warning("[OCR] could not initialize RapidOCR: {}", exc)
        return None
    return _engine


def find_module_via_ocr(
    screenshot: np.ndarray,
    module_name: str,
    panel_left: int,
    panel_top: int,
    panel_width: int,
    panel_height: int,
) -> Optional[Tuple[int, int]]:
    """Find a module label in the left panel using OCR.

    Args:
        screenshot: Full-screen capture (BGR).
        module_name: Expected text (e.g. "Service").
        panel_left, panel_top, panel_width, panel_height: Bounds of the
            left navigation panel in screen coordinates.

    Returns:
        (screen_x, screen_y) — center of the matched text on screen, or None.
    """
    engine = _get_engine()
    if engine is None:
        return None

    # Crop to left panel
    img_h, img_w = screenshot.shape[:2]
    x1 = max(0, panel_left)
    y1 = max(0, panel_top)
    x2 = min(img_w, panel_left + panel_width)
    y2 = min(img_h, panel_top + panel_height)
    panel = screenshot[y1:y2, x1:x2]
    if panel.size == 0:
        logger.warning("[OCR] panel crop is empty.")
        return None

    try:
        result, _elapsed = engine(panel)
    except Exception as exc:
        logger.warning("[OCR] inference failed: {}", exc)
        return None

    if not result:
        logger.warning("[OCR] no text detected in left panel.")
        return None

    target = module_name.strip().lower()
    matches: List[Tuple[int, int, float, str]] = []  # (sx, sy, conf, raw_text)

    for entry in result:
        # RapidOCR returns [box, text, confidence] per detection
        try:
            box, text, conf = entry[0], entry[1], entry[2]
        except (IndexError, TypeError):
            continue
        if not text:
            continue
        t = text.strip().lower()
        # Exact match preferred; allow detected text that IS the target
        # (RapidOCR typically returns the menu label exactly).
        if t != target:
            continue

        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        # Convert from panel coords back to screen coords
        screen_x = int(x1 + cx)
        screen_y = int(y1 + cy)
        matches.append((screen_x, screen_y, float(conf), text))

    if not matches:
        # Log up to ~20 candidates for debugging
        sample = []
        for entry in result[:20]:
            try:
                sample.append(f"'{entry[1]}'")
            except Exception:
                continue
        logger.warning(
            "[OCR] '{}' not found in left panel. Detected {} text item(s): {}",
            module_name, len(result), ", ".join(sample),
        )
        return None

    # Highest confidence wins; topmost on tie
    matches.sort(key=lambda m: (-m[2], m[1]))
    sx, sy, conf, txt = matches[0]
    logger.info(
        "[OCR] found '{}' at screen ({}, {}) conf={:.2f}",
        txt, sx, sy, conf,
    )
    return sx, sy
