"""Local text disambiguator using rendered-text template matching.

Used as a final no-network fallback when both Gemini and Claude APIs
are unavailable or rate-limited. Renders the EXACT target text as an
image and scores each highlighted row by template-matching correlation.

The row whose row-strip best matches the rendered template is the most
likely exact match. This works because:
  - 'Sale Statement' template matched against 'Sale Statement' row → high score
  - 'Sale Statement' template matched against 'Sale Allocation Statement'
    row → lower score (extra 'Allocation' breaks the pixel pattern)
  - 'Sale Statement' template matched against 'Lost Sale Statement' → lower
    score (extra 'Lost' offsets the pattern)

No external dependencies beyond OpenCV + Pillow (already in requirements).
"""

from typing import List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from automation.ocv_text_finder import _render_text_template


# Font sizes to try when rendering the template — Excellon menu items
# are typically rendered at ~12-14px on a Full-HD display.
_FONT_SIZES = (12, 13, 14, 11, 15)

# Vertical padding around each row's highlight center (pixels)
_ROW_HALF_HEIGHT = 14

# Minimum correlation score for the disambiguator to commit to a pick.
# Below this, we're not confident enough and let the next fallback decide.
_MIN_CONFIDENCE = 0.55

# How much higher the best score must be vs the second-best (margin)
_MIN_MARGIN = 0.05

# When a window is narrow, the menu may truncate text (e.g. 'Sale Statement'
# → 'Sale State...'). We try progressive prefixes of the target down to this
# fraction of its length so the template still matches truncated rows.
_MIN_PREFIX_FRACTION = 0.7


def disambiguate_by_template(
    screenshot: np.ndarray,
    regions: List[Tuple[int, int, float, int]],
    report_name: str,
    panel_left: int,
    panel_w: int,
) -> Optional[Tuple[int, int]]:
    """Pick the highlighted row whose text best matches `report_name`.

    Args:
        screenshot: Full screen capture (BGR).
        regions: List of (sx, sy, area, highlight_width) from highlight
            detector — one per highlighted row.
        report_name: The exact text we're looking for.
        panel_left, panel_w: Bounds of the navigation panel in screen px.

    Returns:
        (sx, sy) of the best-scoring row, or None if no row crosses the
        confidence threshold.
    """
    if not regions:
        return None

    img_h, img_w = screenshot.shape[:2]

    # Build a set of text variants:
    #   - The full target text.
    #   - Progressive prefixes (down to _MIN_PREFIX_FRACTION of length) to
    #     handle narrow windows that truncate labels (e.g. 'Sale Statement'
    #     → 'Sale State...').
    target = report_name.strip()
    variants = [target]
    min_len = max(5, int(round(len(target) * _MIN_PREFIX_FRACTION)))
    for end in range(len(target) - 1, min_len - 1, -1):
        prefix = target[:end].rstrip()
        if prefix and prefix != variants[-1]:
            variants.append(prefix)

    # Pre-render templates at a few font sizes for each variant.
    templates: list[tuple[np.ndarray, int, str]] = []
    for variant in variants:
        for fs in _FONT_SIZES:
            try:
                tpl = _render_text_template(variant, font_size=fs)
                templates.append((tpl, fs, variant))
            except Exception:
                continue
    if not templates:
        logger.warning("[Local disambiguator] could not render any templates.")
        return None

    scores: list[float] = []
    for sx, sy, _area, _w in regions:
        ry1 = max(0, sy - _ROW_HALF_HEIGHT)
        ry2 = min(img_h, sy + _ROW_HALF_HEIGHT)
        rx1 = max(0, panel_left)
        rx2 = min(img_w, panel_left + panel_w)
        row_img = screenshot[ry1:ry2, rx1:rx2]
        if row_img.size == 0:
            scores.append(0.0)
            continue

        row_gray = cv2.cvtColor(row_img, cv2.COLOR_BGR2GRAY)

        max_score = 0.0
        for tpl, _fs, _variant in templates:
            t_h, t_w = tpl.shape[:2]
            if t_h > row_gray.shape[0] or t_w > row_gray.shape[1]:
                continue
            try:
                res = cv2.matchTemplate(row_gray, tpl, cv2.TM_CCOEFF_NORMED)
                _, mv, _, _ = cv2.minMaxLoc(res)
                if mv > max_score:
                    max_score = float(mv)
            except Exception:
                continue
        scores.append(max_score)

    logger.info(
        "[Local disambiguator] scores for '{}': {}",
        report_name, [f"{s:.2f}" for s in scores],
    )

    if not scores:
        return None

    # Find best and runner-up
    sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    best_i = sorted_idx[0]
    best_score = scores[best_i]
    second_score = scores[sorted_idx[1]] if len(sorted_idx) > 1 else 0.0
    margin = best_score - second_score

    if best_score < _MIN_CONFIDENCE:
        logger.warning(
            "[Local disambiguator] best score {:.2f} below threshold {:.2f} — "
            "no confident pick.",
            best_score, _MIN_CONFIDENCE,
        )
        return None

    if margin < _MIN_MARGIN and len(scores) > 1:
        logger.warning(
            "[Local disambiguator] best={:.2f} runner-up={:.2f} margin={:.2f} "
            "too small — no confident pick.",
            best_score, second_score, margin,
        )
        return None

    sx, sy, _, _ = regions[best_i]
    logger.info(
        "[Local disambiguator] picked row #{} (score={:.2f}, margin={:.2f}) at ({},{}).",
        best_i + 1, best_score, margin, sx, sy,
    )
    return sx, sy
