"""Anthropic Claude Haiku 4.5 fallback for menu-tree disambiguation.

Used when Gemini Vision is rate-limited (429) or otherwise fails.
Mirrors the row-OCR and index-pick functions in `gemini_verifier.py`
so the chain in collect_results.py can swap one for the other without
changing call shapes.
"""

import base64
import re
from typing import List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from config.settings import settings


_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 32


def _img_to_b64_png(img_bgr: np.ndarray) -> Optional[str]:
    """Encode a BGR numpy array to base64 PNG."""
    try:
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        ok, buf = cv2.imencode(".png", rgb)
        return base64.b64encode(buf.tobytes()).decode("utf-8") if ok else None
    except Exception:
        return None


def _client():
    """Return an Anthropic client, or None if the key/SDK isn't available."""
    if not settings.anthropic_api_key:
        logger.debug("[Claude] anthropic_api_key not set — skipping.")
        return None
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=settings.anthropic_api_key)
    except ImportError:
        logger.warning("[Claude] anthropic SDK not installed — skipping.")
        return None
    except Exception as exc:
        logger.warning("[Claude] could not create client: {}", exc)
        return None


def _send_image_text(client, img_b64: str, prompt: str) -> Optional[str]:
    """Send a single image+prompt request to Claude. Returns reply text or None."""
    try:
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        if not resp.content:
            return None
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text.strip()
        return None
    except Exception as exc:
        logger.warning("[Claude] API call failed: {}", exc)
        return None


def anthropic_row_ocr(
    screenshot: np.ndarray,
    regions: List[Tuple[int, int, float, int]],
    report_name: str,
    panel_left: int,
    panel_w: int,
) -> Optional[Tuple[int, int]]:
    """For each highlighted row, ask Claude YES/NO whether it is the exact match.

    Returns the (sx, sy) of the first row that gets a YES, or None.
    """
    client = _client()
    if client is None:
        return None

    img_h, img_w = screenshot.shape[:2]

    for sx, sy, _area, _w in regions:
        ry1 = max(0, sy - 14)
        ry2 = min(img_h, sy + 14)
        rx1 = max(0, panel_left)
        rx2 = min(img_w, panel_left + panel_w)
        row_img = screenshot[ry1:ry2, rx1:rx2]
        if row_img.size == 0:
            continue

        # Scale 3× so small UI text is readable
        row_scaled = cv2.resize(row_img, None, fx=3, fy=3,
                                interpolation=cv2.INTER_LINEAR)
        img_b64 = _img_to_b64_png(row_scaled)
        if not img_b64:
            continue

        prompt = (
            f"Read the text visible in this image (a single row from a "
            f"Windows navigation tree). "
            f"Does the row's text say EXACTLY '{report_name}' "
            f"(case-insensitive, ignore icons and trailing whitespace)? "
            f"Reply with ONLY 'YES' or 'NO'."
        )

        answer = _send_image_text(client, img_b64, prompt)
        if answer is None:
            # API failure — bail out so the next strategy runs
            return None
        upper = answer.upper()
        logger.info(
            "[Claude row-OCR] '{}' at ({},{}) → '{}'",
            report_name, sx, sy, answer,
        )
        if "YES" in upper:
            return sx, sy

    return None


def anthropic_find_module(
    screenshot: np.ndarray,
    module_name: str,
    panel_left: int,
    panel_top: int,
    panel_width: int,
    panel_height: int,
) -> Optional[Tuple[int, int]]:
    """Ask Claude Haiku to locate a module label in the left navigation panel.

    Used as the final fallback after UIA and OCR both fail to find the
    correct module (e.g. 'Service' on a Excellon build where text fragments
    confuse UIA descendants).

    Returns (screen_x, screen_y) — center of the module text on screen.
    """
    client = _client()
    if client is None:
        return None

    img_h, img_w = screenshot.shape[:2]
    x1 = max(0, panel_left)
    y1 = max(0, panel_top)
    x2 = min(img_w, panel_left + panel_width)
    y2 = min(img_h, panel_top + panel_height)
    panel = screenshot[y1:y2, x1:x2]
    if panel.size == 0:
        return None

    try:
        scaled = cv2.resize(panel, None, fx=2, fy=2,
                            interpolation=cv2.INTER_LINEAR)
    except Exception:
        scaled = panel

    img_b64 = _img_to_b64_png(scaled)
    if not img_b64:
        return None

    crop_h, crop_w = panel.shape[:2]
    scale_factor = 2  # we sent the image scaled 2×
    prompt = (
        f"This image shows the LEFT navigation panel of a Windows "
        f"application (zoomed {scale_factor}×). It is a vertical list of "
        f"top-level menu items (each row has an icon, a text label, and an "
        f"expand chevron). "
        f"\n\nFind the menu row whose label is EXACTLY '{module_name}' "
        f"(case-insensitive). Ignore any tooltips, announcements, or other "
        f"places where this word may appear — return ONLY the row that is a "
        f"top-level menu item in the navigation list. "
        f"\n\nReturn the center pixel coordinates of that label within THIS "
        f"image as: x,y (e.g. '95,310'). The image is {scaled.shape[1]} "
        f"pixels wide and {scaled.shape[0]} pixels tall. If the label is "
        f"not visible, return: NOT_FOUND"
    )

    answer = _send_image_text(client, img_b64, prompt)
    if not answer:
        return None
    logger.info("[Claude module] response for '{}': '{}'", module_name, answer)
    if "NOT_FOUND" in answer.upper():
        return None
    m = re.search(r"(\d+)\s*,\s*(\d+)", answer)
    if not m:
        return None
    # Coords are in the scaled (2×) image; convert back to original panel
    cx_scaled = int(m.group(1))
    cy_scaled = int(m.group(2))
    cx_panel = cx_scaled // scale_factor
    cy_panel = cy_scaled // scale_factor
    # Clamp to panel bounds
    cx_panel = max(0, min(cx_panel, crop_w - 1))
    cy_panel = max(0, min(cy_panel, crop_h - 1))
    sx = x1 + cx_panel
    sy = y1 + cy_panel
    logger.info(
        "[Claude module] '{}' located at screen ({}, {})",
        module_name, sx, sy,
    )
    return sx, sy


def anthropic_pick_by_index(
    panel_crop: np.ndarray,
    regions: List[Tuple[int, int, float, int]],
    report_name: str,
) -> Optional[Tuple[int, int]]:
    """Ask Claude which numbered item (1..N top-to-bottom) is the exact match."""
    client = _client()
    if client is None:
        return None
    if panel_crop is None or panel_crop.size == 0:
        return None

    try:
        scaled = cv2.resize(panel_crop, None, fx=2, fy=2,
                            interpolation=cv2.INTER_LINEAR)
    except Exception:
        return None

    img_b64 = _img_to_b64_png(scaled)
    if not img_b64:
        return None

    n = len(regions)
    n_words = len(report_name.strip().split())
    prompt = (
        f"This image shows a navigation tree panel (zoomed 2×). "
        f"There are {n} highlighted tree item(s), numbered 1 to {n} "
        f"from TOP to BOTTOM. "
        f"I need the item whose COMPLETE text is EXACTLY '{report_name}' "
        f"({n_words} word(s), case-insensitive). "
        f"\n\nKEY VISUAL CLUE: search highlights only the matched words "
        f"in yellow/amber. The EXACT match has EVERY word highlighted "
        f"with NO plain (unhighlighted) text between them. Items that "
        f"are NOT the exact match contain extra plain words between the "
        f"highlighted ones (e.g. 'Sale Allocation Statement' has "
        f"'Allocation' as plain text). "
        f"\n\nReply with ONLY the item number (1 to {n})."
    )

    answer = _send_image_text(client, img_b64, prompt)
    if not answer:
        return None
    logger.info("[Claude index] response for '{}': '{}'", report_name, answer)
    m = re.search(r"\b(\d+)\b", answer)
    if not m:
        return None
    idx = int(m.group(1)) - 1
    idx = max(0, min(idx, n - 1))
    sx, sy, _, _ = regions[idx]
    logger.info("[Claude index] chose item {} → ({},{})", idx + 1, sx, sy)
    return sx, sy
