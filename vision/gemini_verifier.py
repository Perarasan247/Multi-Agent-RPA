"""Gemini-based visual verification for menu tree selection."""

import base64
import io

import cv2
import numpy as np
import google.generativeai as genai
from loguru import logger

from config.settings import settings


def verify_selection_with_gemini(
    screenshot: np.ndarray,
    report_name: str,
    folder_path: list[str],
) -> bool:
    """Use Gemini Vision to verify correct item is highlighted.

    Sends a cropped screenshot of the navigation panel to Gemini
    and asks it to confirm the correct item is selected.

    Args:
        screenshot: BGR numpy array of the left panel area.
        report_name: Expected report name to be highlighted.
        folder_path: List of folder names forming the expected path.

    Returns:
        True if Gemini confirms the correct selection.
        False on rejection or any API error (fail-safe).
    """
    try:
        genai.configure(api_key=settings.gemini_api_key)

        # Convert BGR numpy array to base64 PNG
        rgb_image = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
        success, buffer = cv2.imencode(".png", rgb_image)
        if not success:
            logger.error("Failed to encode screenshot for Gemini.")
            return False

        image_bytes = buffer.tobytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            f"This is a screenshot of a Windows application menu tree. "
            f"I am looking for the item '{report_name}' which should be "
            f"inside the folder path: {' > '.join(folder_path)}. "
            f"Is this item fully highlighted in blue and is it the deepest "
            f"item (the actual file, not a folder)? "
            f"Answer only YES or NO."
        )

        model = genai.GenerativeModel("gemini-2.0-flash")

        # Build image part for the API
        image_part = {
            "mime_type": "image/png",
            "data": image_b64,
        }

        response = model.generate_content([prompt, image_part])
        response_text = response.text.strip().upper()

        logger.info(
            "Gemini verification for '{}': response='{}'",
            report_name, response_text,
        )

        return "YES" in response_text

    except Exception as exc:
        logger.error(
            "Gemini verification failed for '{}': {}",
            report_name, exc,
        )
        # Fail-safe: return False on error
        return False


def find_item_coordinates_with_gemini(
    panel_crop: np.ndarray,
    report_name: str,
    panel_offset_x: int = 0,
    panel_offset_y: int = 0,
) -> tuple[int, int] | None:
    """Ask Gemini to locate a named tree item inside a cropped panel image.

    The image passed must already be cropped to the left navigation panel so
    Gemini cannot confuse it with other occurrences of the report name elsewhere
    on screen (e.g. Recently Used section). The returned coordinates are
    converted back to full-screen coords using the panel offsets.

    Args:
        panel_crop: BGR numpy array of the left navigation panel only.
        report_name: The report name to find.
        panel_offset_x: Screen X of the crop's left edge.
        panel_offset_y: Screen Y of the crop's top edge.

    Returns:
        (screen_x, screen_y) pixel coordinates of the item center, or None.
    """
    try:
        if not settings.gemini_api_key:
            logger.debug("Gemini key not set — skipping coordinate search.")
            return None

        if panel_crop is None or panel_crop.size == 0:
            logger.warning("Gemini: panel crop is empty.")
            return None

        genai.configure(api_key=settings.gemini_api_key)

        rgb_image = cv2.cvtColor(panel_crop, cv2.COLOR_BGR2RGB)
        success, buffer = cv2.imencode(".png", rgb_image)
        if not success:
            return None

        image_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")

        words = report_name.strip().split()
        n_words = len(words)
        prompt = (
            f"This image shows ONLY the navigation tree panel of a Windows application. "
            f"The search bar has been cropped out — ignore any text input box. "
            f"Find the tree item (leaf node with a file icon) whose text is EXACTLY "
            f"'{report_name}' (case-insensitive). "
            f"EXACT means the item text has EXACTLY {n_words} word(s) matching "
            f"'{report_name}' — no extra words before or after. "
            f"Examples of what NOT to pick: "
            f"if the search is 'Purchase Statement', do NOT pick "
            f"'Purchase Order Statement' or 'Purchase Invoice Statement'. "
            f"If the search is 'Sales MIS Report', do NOT pick 'Sales MIS Report New'. "
            f"The correct item has an orange, yellow, amber, or blue highlight. "
            f"Return ONLY the center pixel coordinates within THIS cropped image as: x,y "
            f"(e.g. 95,87). If no exact match exists, return: NOT_FOUND"
        )

        model = genai.GenerativeModel("gemini-2.0-flash")
        image_part = {"mime_type": "image/png", "data": image_b64}
        response = model.generate_content([prompt, image_part])
        text = response.text.strip()

        logger.info("Gemini coordinate response for '{}': '{}'", report_name, text)

        if "NOT_FOUND" in text.upper():
            return None

        import re
        match = re.search(r"(\d+)\s*,\s*(\d+)", text)
        if match:
            cx = int(match.group(1)) + panel_offset_x
            cy = int(match.group(2)) + panel_offset_y
            logger.info(
                "Gemini found '{}' at panel-relative coords → screen ({}, {}).",
                report_name, cx, cy,
            )
            return cx, cy

        logger.warning("Could not parse coordinates from Gemini response: '{}'", text)
        return None

    except Exception as exc:
        logger.error("Gemini coordinate search failed: {}", exc)
        return None
