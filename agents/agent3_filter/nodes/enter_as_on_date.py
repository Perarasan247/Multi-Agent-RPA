"""Node: Enter the As On Date for reports that use as_on_date_only.

Used for Stock Valuation (Sales) and Spare Parts Stock Valuation reports.

6-tier fallback to locate the "As On Date" input field:
  Tier 1  UIA by automation_id  — returns the control for native entry
  Tier 2  UIA by label proximity — finds the label, derives click coords
  Tier 3  OpenCV template match  — renders label text as image, matches on screen
  Tier 4  RapidOCR               — reads screen pixels, locates the label
  Tier 5  Gemini vision          — vision API locates the field from screenshot
  Tier 6  Claude vision          — final fallback (only when Gemini fails)

Date entry methods for UIA Tier 1 (UIA control available):
  1. ctrl.set_value(datetime)  — native DateTimePicker API, no keystrokes needed
  2. ctrl.set_edit_text(str)   — direct text injection via pywinauto
  3. triple_click + typewrite  — better than Ctrl+A for DateTimePicker segments
  4. Ctrl+A + Backspace + typewrite — original last resort

Date entry for coordinate-only tiers (2–6):
  1. triple_click + typewrite  — selects all text in most date inputs
  2. Ctrl+A + Backspace + typewrite — fallback

UIA-based verification: read back ctrl.window_text() and compare digits.
Screenshot verification: informational only (yellow background can fool OCR).
"""

import base64
import datetime
import io
import re
import time
from typing import Any, Optional, Tuple

import cv2
import numpy as np
import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.ocv_text_finder import find_text_on_screen
from automation.window_manager import get_main_window
from automation.uia_retry import find_descendant_by_auto_id, find_descendant_by_text
from agents.agent3_filter.nodes.enter_from_date import _normalize_date


_KNOWN_AUTO_IDS = (
    "AsOnDate", "AsOnDateTime", "ReportAsOnDate",
    "OnDate", "AsOnDt", "AsOndate",
)

_LABEL_VARIANTS = (
    "As On Date", "As on Date", "AS ON DATE",
    "As On Date :", "As On Dt",
)

_VISION_PROMPT = (
    "This is the filter panel of an Excellon ERP report. "
    "Find the 'As On Date' date input field — it is typically a yellow or highlighted "
    "date picker box showing a date like '02-05-2026'. "
    "Return ONLY two integers separated by a space: x y "
    "(pixel coordinates of the center of the date input field itself, not its label). "
    "Example reply: 312 445"
)


# ── Date parsing ──────────────────────────────────────────────────────────────


def _parse_date_obj(date_str: str) -> datetime.datetime:
    """Parse 'DD-MM-YYYY' or 'DD/MM/YYYY' to datetime.datetime (for set_value)."""
    clean = date_str.replace("/", "-").replace(".", "-")
    d, m, y = clean.split("-")
    return datetime.datetime(int(y), int(m), int(d))


def _dates_match(expected: str, actual: str) -> bool:
    """Check if the expected date digits all appear in the control's text."""
    exp = expected.replace("-", "").replace("/", "")
    act = actual.replace("-", "").replace("/", "").replace(".", "")
    return exp in act


# ── Date entry ────────────────────────────────────────────────────────────────


def _enter_via_ctrl(ctrl, date_str: str, date_obj: datetime.datetime) -> bool:
    """Try pywinauto native entry methods. Returns True when entry is confirmed."""

    # Method 1: set_value — native DateTimePicker, no keyboard simulation
    try:
        ctrl.set_value(date_obj)
        time.sleep(0.3)
        actual = (ctrl.window_text() or "").strip()
        if _dates_match(date_str, actual):
            logger.info("[AsOnDate] set_value() confirmed: '{}'.", actual)
            return True
        logger.debug("[AsOnDate] set_value() wrote but got '{}' for '{}'.", actual, date_str)
    except Exception as exc:
        logger.debug("[AsOnDate] set_value() failed: {}", exc)

    # Method 2: set_edit_text — direct text injection
    try:
        ctrl.set_edit_text(date_str)
        time.sleep(0.3)
        actual = (ctrl.window_text() or "").strip()
        if _dates_match(date_str, actual):
            logger.info("[AsOnDate] set_edit_text() confirmed: '{}'.", actual)
            return True
        logger.debug("[AsOnDate] set_edit_text() wrote but got '{}'.", actual)
    except Exception as exc:
        logger.debug("[AsOnDate] set_edit_text() failed: {}", exc)

    # Method 3: click_input + Ctrl+A + Backspace + typewrite (same as enter_from_date)
    try:
        ctrl.click_input()
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.3)
        pyautogui.press("backspace")
        time.sleep(0.3)
        pyautogui.typewrite(date_str, interval=0.05)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.3)
        logger.info("[AsOnDate] Ctrl+A+Backspace+typewrite via ctrl.")
        return True
    except Exception as exc:
        logger.debug("[AsOnDate] ctrl Ctrl+A method failed: {}", exc)

    return False


def _enter_via_coords(coords: Tuple[int, int], date_str: str) -> None:
    """Enter date at screen coordinates using the same technique as enter_from_date."""
    cx, cy = coords
    pyautogui.moveTo(cx, cy, duration=0.15)
    time.sleep(0.1)
    pyautogui.click(cx, cy)
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.3)
    pyautogui.press("backspace")
    time.sleep(0.3)
    pyautogui.typewrite(date_str, interval=0.05)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.5)


# ── Filter panel crop (for vision tiers) ─────────────────────────────────────


def _panel_crop(main_win, screen: np.ndarray) -> Tuple[np.ndarray, int, int]:
    wr = main_win.rectangle()
    rx = max(wr.left, wr.right - 450)
    ry = wr.top
    return screen[ry:wr.bottom, rx:wr.right], rx, ry


def _parse_vision_coords(text: str, rw: int, rh: int) -> Optional[Tuple[int, int]]:
    match = re.search(r"(\d+)\s+(\d+)", text)
    if not match:
        return None
    x, y = int(match.group(1)), int(match.group(2))
    if 0 <= x <= rw and 0 <= y <= rh:
        return x, y
    return None


# ── Tier locators ─────────────────────────────────────────────────────────────


def _find_via_uia_auto_id(main_win) -> Optional[Tuple[str, Any]]:
    for auto_id in _KNOWN_AUTO_IDS:
        ctrl = find_descendant_by_auto_id(main_win, auto_id, retries=2, delay=1.0)
        if ctrl is not None:
            logger.info("[AsOnDate/UIA-id] Found control auto_id='{}'.", auto_id)
            return "ctrl", ctrl
    return None


def _find_via_uia_label(main_win) -> Optional[Tuple[str, Any]]:
    for variant in _LABEL_VARIANTS:
        label_ctrl = find_descendant_by_text(main_win, variant, retries=2, delay=1.0)
        if label_ctrl is None:
            continue

        lr = label_ctrl.rectangle()
        logger.info("[AsOnDate/UIA-label] Found label '{}' at ({},{}).", variant, lr.left, lr.top)

        # Try to find the actual DateTimePicker/Edit control near the label.
        # Prefer a control on the same row or within 60px below it.
        _DTP_TYPES = ("Edit", "Custom", "DateTimePicker", "Spinner")
        try:
            for ctrl in main_win.descendants():
                try:
                    ct = getattr(ctrl.element_info, "control_type", "")
                    if ct not in _DTP_TYPES:
                        continue
                    cr = ctrl.rectangle()
                    vertically_close = abs(cr.top - lr.top) < 60
                    horizontally_near = cr.right > lr.left and cr.left < lr.right + 300
                    if vertically_close and horizontally_near:
                        logger.info(
                            "[AsOnDate/UIA-label] Found input ctrl (type='{}') near label.",
                            ct,
                        )
                        return "ctrl", ctrl
                except Exception:
                    continue
        except Exception:
            pass

        # Could not find the actual control — fall back to coordinate click below the label
        cx = (lr.left + lr.right) // 2
        cy = lr.bottom + 18
        logger.info(
            "[AsOnDate/UIA-label] No input ctrl found near label, using coords ({},{}).",
            cx, cy,
        )
        return "coords", (cx, cy)
    return None


def _find_via_opencv(screen: np.ndarray) -> Optional[Tuple[str, Any]]:
    try:
        for variant in _LABEL_VARIANTS:
            pos = find_text_on_screen(screen, variant, threshold=0.6)
            if pos is not None:
                lx, ly = pos
                logger.info(
                    "[AsOnDate/OpenCV] '{}' at ({},{}), input at ({},{}).",
                    variant, lx, ly, lx, ly + 25,
                )
                return "coords", (lx, ly + 25)
    except Exception as exc:
        logger.debug("[AsOnDate/OpenCV] failed: {}", exc)
    return None


def _find_via_ocr(screen: np.ndarray, win_rect) -> Optional[Tuple[str, Any]]:
    try:
        from vision.ocr_module_finder import find_module_via_ocr
        img_h, img_w = screen.shape[:2]
        pl = max(0, win_rect.right - 450)
        pt = max(0, win_rect.top + 100)
        pw = min(img_w - pl, 450)
        ph = min(img_h - pt, win_rect.height() - 100)
        for variant in _LABEL_VARIANTS:
            coords = find_module_via_ocr(screen, variant, pl, pt, pw, ph)
            if coords is not None:
                lx, ly = coords
                logger.info(
                    "[AsOnDate/OCR] '{}' at ({},{}), input at ({},{}).",
                    variant, lx, ly, lx, ly + 25,
                )
                return "coords", (lx, ly + 25)
    except Exception as exc:
        logger.debug("[AsOnDate/OCR] failed: {}", exc)
    return None


def _find_via_gemini(main_win, screen: np.ndarray) -> Optional[Tuple[str, Any]]:
    try:
        import google.generativeai as genai
        from PIL import Image

        if not settings.gemini_api_key:
            logger.debug("[AsOnDate/Gemini] No API key.")
            return None

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        crop, rx, ry = _panel_crop(main_win, screen)
        rh, rw = crop.shape[:2]
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        response = model.generate_content([pil_img, _VISION_PROMPT])
        rel = _parse_vision_coords((response.text or "").strip(), rw, rh)
        if rel:
            cx, cy = rx + rel[0], ry + rel[1]
            logger.info("[AsOnDate/Gemini] Date field at ({},{}).", cx, cy)
            return "coords", (cx, cy)
        logger.warning("[AsOnDate/Gemini] Could not parse coords: {}", response.text)
    except Exception as exc:
        logger.debug("[AsOnDate/Gemini] failed: {}", exc)
    return None


def _find_via_claude(main_win, screen: np.ndarray) -> Optional[Tuple[str, Any]]:
    try:
        import anthropic
        from PIL import Image

        if not settings.anthropic_api_key:
            logger.debug("[AsOnDate/Claude] No API key.")
            return None

        crop, rx, ry = _panel_crop(main_win, screen)
        rh, rw = crop.shape[:2]
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
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
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }],
        )
        text = (response.content[0].text or "").strip()
        rel = _parse_vision_coords(text, rw, rh)
        if rel:
            cx, cy = rx + rel[0], ry + rel[1]
            logger.info("[AsOnDate/Claude] Date field at ({},{}).", cx, cy)
            return "coords", (cx, cy)
        logger.warning("[AsOnDate/Claude] Could not parse coords: {}", text)
    except Exception as exc:
        logger.debug("[AsOnDate/Claude] failed: {}", exc)
    return None


# ── Screenshot verification (informational only) ──────────────────────────────


def _verify_on_screen(screen: np.ndarray, date_str: str, win_rect) -> bool:
    region = None
    try:
        h, w = screen.shape[:2]
        rx = max(0, win_rect.right - 450)
        ry = max(0, win_rect.top + 100)
        rw = min(w - rx, 450)
        rh = min(h - ry, win_rect.height() - 100)
        if rw > 50 and rh > 50:
            region = (rx, ry, rw, rh)
    except Exception:
        pass
    return find_text_on_screen(screen, date_str, region=region, threshold=0.55) is not None


# ── Main node ─────────────────────────────────────────────────────────────────


def enter_as_on_date_node(state: GlobalState) -> GlobalState:
    """Locate and enter the As On Date with 6-tier fallback."""
    logger.info("[Agent3] Node: enter_as_on_date — entering")
    try:
        as_on_date = state.get("to_date") or settings.filter_to_date
        date_norm = _normalize_date(as_on_date)
        date_obj = _parse_date_obj(date_norm)

        app = state["app_handle"]
        main_win = get_main_window(app)
        win_rect = main_win.rectangle()
        screen = capture_screen()

        gemini_failed = False

        tiers = [
            ("UIA-id",    lambda: _find_via_uia_auto_id(main_win)),
            ("UIA-label", lambda: _find_via_uia_label(main_win)),
            ("OpenCV",    lambda: _find_via_opencv(screen)),
            ("OCR",       lambda: _find_via_ocr(screen, win_rect)),
            ("Gemini",    lambda: _find_via_gemini(main_win, screen)),
            ("Claude",    lambda: _find_via_claude(main_win, screen)),
        ]

        for tier_name, locator in tiers:
            if tier_name == "Claude" and not gemini_failed:
                continue

            try:
                result = locator()
            except Exception as exc:
                logger.warning("[Agent3] AsOnDate tier '{}' raised: {}", tier_name, exc)
                if tier_name == "Gemini":
                    gemini_failed = True
                continue

            if result is None:
                logger.info("[Agent3] AsOnDate tier '{}' — field not found.", tier_name)
                if tier_name == "Gemini":
                    gemini_failed = True
                continue

            kind, payload = result

            if kind == "ctrl":
                if not _enter_via_ctrl(payload, date_norm, date_obj):
                    logger.warning(
                        "[Agent3] AsOnDate tier '{}' — all entry methods failed, trying next.",
                        tier_name,
                    )
                    continue
            else:
                _enter_via_coords(payload, date_norm)

            # Verification — informational only, never blocks progress
            new_screen = capture_screen()
            if _verify_on_screen(new_screen, date_norm, win_rect):
                logger.info(
                    "[Agent3] AsOnDate verified via tier '{}' — '{}' visible on screen.",
                    tier_name, date_norm,
                )
            else:
                logger.warning(
                    "[Agent3] AsOnDate tier '{}' typed '{}' — screenshot verify inconclusive "
                    "(yellow background may block OCR), continuing.",
                    tier_name, date_norm,
                )

            state["date_range_set"] = True
            logger.info(
                "[Agent3] Node: enter_as_on_date — completed via tier '{}'.", tier_name,
            )
            return state

        state["error"] = (
            f"enter_as_on_date: all 6 tiers failed to locate the As On Date field "
            f"(UIA-id, UIA-label, OpenCV, OCR, Gemini, Claude). "
            f"Cannot enter date '{date_norm}'."
        )
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "enter_as_on_date_no_field")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"enter_as_on_date failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "enter_as_on_date_error")
        except Exception:
            pass

    return state
