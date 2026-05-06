"""Node: Handle tax-related checkboxes based on report config.

5-tier fallback per checkbox label:
  Tier 1  UIA (automation ID)  — fastest, no text dependency
  Tier 2  UIA (text search)    — label variants with/without trailing s
  Tier 3  OCR (RapidOCR)       — find label on screen, click checkbox box
  Tier 4  Gemini               — vision API locates checkbox from screenshot
  Tier 5  Claude               — vision fallback (only when Gemini fails)

Click methods tried in order for UIA tiers:
  1. ctrl.check()       — native pywinauto, no coordinates needed
  2. ctrl.click_input() — pywinauto click directly to the UIA element
  3. pyautogui.click()  — coordinate fallback from control rect

After every UIA click, toggle state is re-read to verify the box is
actually checked. If still unchecked the tier is skipped and the next
one tries. Claude only fires when Gemini returns None or raises.
"""

import base64
import io
import re
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot
from automation.window_manager import get_main_window
from automation.uia_retry import find_descendant_by_auto_id, find_descendant_by_text


# ── Label / ID helpers ────────────────────────────────────────────────────────


def _text_variants(label: str) -> list[str]:
    """Return candidate label strings (with / without trailing s)."""
    variants = [label]
    if label.endswith("s"):
        variants.append(label[:-1])
    else:
        variants.append(label + "s")
    return list(dict.fromkeys(variants))


def _auto_id_candidates(label: str) -> list[str]:
    """Derive likely UIA automation IDs from a label string.

    "Show Taxes"       → ["ShowTaxes", "showTaxes", "chkShowTaxes", "ShowTaxe" ...]
    "Show Tax Details" → ["ShowTaxDetails", "ShowTaxDetail", "chkShowTaxDetails" ...]
    """
    words = label.split()
    joined = "".join(words)
    title  = "".join(w.title() for w in words)
    camel  = words[0].lower() + "".join(w.title() for w in words[1:])
    ids = [joined, title, camel, joined.lower(), "chk" + title, "chk" + joined]
    if joined.endswith("s"):
        ids += [joined[:-1], title[:-1], "chk" + title[:-1]]
    return list(dict.fromkeys(ids))


# ── Click + verify helpers ────────────────────────────────────────────────────


def _click_ctrl(ctrl) -> None:
    """Click a UIA control: check() → click_input() → pyautogui fallback."""
    try:
        ctrl.check()
        return
    except Exception:
        pass
    try:
        ctrl.click_input()
        return
    except Exception:
        pass
    r = ctrl.rectangle()
    pyautogui.click(r.left + 10, r.top + r.height() // 2)


def _is_checked(ctrl) -> Optional[bool]:
    """Return True/False from toggle state, or None if unreadable."""
    try:
        state = ctrl.get_toggle_state()
        if state == 1:
            return True
        if state == 0:
            return False
    except Exception:
        pass
    return None


# ── Filter panel region ───────────────────────────────────────────────────────


def _panel_region(main_win) -> Tuple[int, int, int, int]:
    """Return (left, top, width, height) of the right-side filter panel."""
    wr = main_win.rectangle()
    left = max(wr.left, wr.right - 450)
    top  = wr.top
    return left, top, wr.right - left, wr.bottom - top


# ── Tier 1: UIA by automation ID ─────────────────────────────────────────────


def _find_via_auto_id(main_win, label: str):
    for auto_id in _auto_id_candidates(label):
        ctrl = find_descendant_by_auto_id(main_win, auto_id, retries=2, delay=0.5)
        if ctrl is not None:
            logger.info("[TaxBox/UIA-id] '{}' via auto_id '{}'.", label, auto_id)
            return ctrl
    return None


# ── Tier 2: UIA by text ───────────────────────────────────────────────────────


def _find_via_text(main_win, label: str):
    for variant in _text_variants(label):
        ctrl = find_descendant_by_text(main_win, variant, retries=3, delay=1.0)
        if ctrl is not None:
            logger.info("[TaxBox/UIA-text] '{}' via text '{}'.", label, variant)
            return ctrl
    return None


# ── Tier 3: OCR ──────────────────────────────────────────────────────────────


def _find_via_ocr(main_win, screen: np.ndarray, label: str) -> Optional[Tuple[int, int]]:
    """Find label text via OCR; return coords of the checkbox box (left of text)."""
    try:
        from vision.ocr_module_finder import find_module_via_ocr
        pl, pt, pw, ph = _panel_region(main_win)
        for variant in _text_variants(label):
            coords = find_module_via_ocr(screen, variant, pl, pt, pw, ph)
            if coords is not None:
                lx, ly = coords
                # In WinForms the checkbox box sits ~20px to the left of the label
                cx = max(0, lx - 20)
                cy = ly
                logger.info(
                    "[TaxBox/OCR] '{}' label at ({},{}), clicking box at ({},{}).",
                    variant, lx, ly, cx, cy,
                )
                return cx, cy
    except Exception as exc:
        logger.debug("[TaxBox/OCR] failed: {}", exc)
    return None


# ── Tier 4 & 5: Vision (Gemini / Claude) ─────────────────────────────────────


def _vision_prompt(label: str) -> str:
    return (
        f"This is a screenshot of a report filter panel in an Excellon ERP application. "
        f"Find the checkbox labeled '{label}'. "
        f"Return ONLY two integers separated by a space: x y "
        f"(pixel coordinates of the center of the checkbox tick-box square itself, "
        f"not the label text next to it). "
        f"Example reply: 142 318"
    )


def _crop_panel(main_win, screen: np.ndarray) -> Tuple[np.ndarray, int, int]:
    pl, pt, pw, ph = _panel_region(main_win)
    return screen[pt:pt + ph, pl:pl + pw], pl, pt


def _parse_vision_coords(text: str, rw: int, rh: int) -> Optional[Tuple[int, int]]:
    match = re.search(r"(\d+)\s+(\d+)", text)
    if not match:
        return None
    x, y = int(match.group(1)), int(match.group(2))
    if 0 <= x <= rw and 0 <= y <= rh:
        return x, y
    return None


def _find_via_gemini(main_win, screen: np.ndarray, label: str) -> Optional[Tuple[int, int]]:
    try:
        import google.generativeai as genai
        from PIL import Image
        from config.settings import settings

        if not settings.gemini_api_key:
            return None

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        crop, rx, ry = _crop_panel(main_win, screen)
        rh, rw = crop.shape[:2]
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        response = model.generate_content([pil_img, _vision_prompt(label)])
        rel = _parse_vision_coords((response.text or "").strip(), rw, rh)
        if rel:
            logger.info("[TaxBox/Gemini] '{}' at ({},{}).", label, rx + rel[0], ry + rel[1])
            return rx + rel[0], ry + rel[1]
        logger.warning("[TaxBox/Gemini] Could not parse coords from: {}", response.text)
    except Exception as exc:
        logger.debug("[TaxBox/Gemini] failed: {}", exc)
    return None


def _find_via_claude(main_win, screen: np.ndarray, label: str) -> Optional[Tuple[int, int]]:
    try:
        import anthropic
        from PIL import Image
        from config.settings import settings

        if not settings.anthropic_api_key:
            return None

        crop, rx, ry = _crop_panel(main_win, screen)
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
                    {"type": "text", "text": _vision_prompt(label)},
                ],
            }],
        )
        text = (response.content[0].text or "").strip()
        rel = _parse_vision_coords(text, rw, rh)
        if rel:
            logger.info("[TaxBox/Claude] '{}' at ({},{}).", label, rx + rel[0], ry + rel[1])
            return rx + rel[0], ry + rel[1]
        logger.warning("[TaxBox/Claude] Could not parse coords from: {}", text)
    except Exception as exc:
        logger.debug("[TaxBox/Claude] failed: {}", exc)
    return None


# ── Tick one checkbox through all tiers ──────────────────────────────────────


def _tick_one(
    main_win,
    label: str,
    screen: np.ndarray,
    gemini_failed: bool,
) -> Tuple[bool, bool]:
    """Find and tick one checkbox label using all tiers.

    Returns (success, updated_gemini_failed).
    """
    tiers = [
        ("UIA-id",   "ctrl",   lambda: _find_via_auto_id(main_win, label)),
        ("UIA-text", "ctrl",   lambda: _find_via_text(main_win, label)),
        ("OCR",      "coords", lambda: _find_via_ocr(main_win, screen, label)),
        ("Gemini",   "coords", lambda: _find_via_gemini(main_win, screen, label)),
        ("Claude",   "coords", lambda: _find_via_claude(main_win, screen, label)),
    ]

    for tier_name, kind, locator in tiers:
        if tier_name == "Claude" and not gemini_failed:
            continue

        try:
            result = locator()
        except Exception as exc:
            logger.warning("[TaxBox] Tier '{}' raised: {}", tier_name, exc)
            if tier_name == "Gemini":
                gemini_failed = True
            continue

        if result is None:
            logger.info("[TaxBox] Tier '{}' — '{}' not found.", tier_name, label)
            if tier_name == "Gemini":
                gemini_failed = True
            continue

        if kind == "ctrl":
            ctrl = result

            # Check if already ticked — skip to avoid unchecking
            if _is_checked(ctrl) is True:
                logger.info("[TaxBox] '{}' already checked — skipping.", label)
                return True, gemini_failed

            _click_ctrl(ctrl)
            time.sleep(0.4)

            checked = _is_checked(ctrl)
            if checked is True:
                logger.info("[TaxBox] '{}' ticked via tier '{}'.", label, tier_name)
                return True, gemini_failed
            if checked is False:
                logger.warning(
                    "[TaxBox] Tier '{}' clicked '{}' but still unchecked — trying next tier.",
                    tier_name, label,
                )
                continue
            # Toggle state unreadable — assume success (non-standard control)
            logger.info(
                "[TaxBox] '{}' clicked via '{}' (toggle state unreadable — assuming OK).",
                label, tier_name,
            )
            return True, gemini_failed

        else:  # coords from OCR or vision
            cx, cy = result
            pyautogui.click(cx, cy)
            time.sleep(0.4)
            # No UIA handle to verify — assume success
            logger.info(
                "[TaxBox] '{}' clicked via tier '{}' at ({},{}).",
                label, tier_name, cx, cy,
            )
            return True, gemini_failed

    logger.error("[TaxBox] All 5 tiers failed for '{}'.", label)
    return False, gemini_failed


# ── Main node ─────────────────────────────────────────────────────────────────


def handle_tax_checkboxes_node(state: GlobalState) -> GlobalState:
    """Tick tax filter checkboxes with 5-tier fallback per label."""
    logger.info("[Agent3] Node: handle_tax_checkboxes — entering")
    try:
        filters = state.get("filters", [])

        if not filters:
            logger.info("[Agent3] No filters configured, skipping checkboxes.")
            state["tax_boxes_handled"] = True
            return state

        app = state["app_handle"]
        main_win = get_main_window(app)

        # Wait for filter panel controls to fully render
        time.sleep(3.0)

        screen = capture_screen()
        gemini_failed = False
        failed = []

        for label in filters:
            success, gemini_failed = _tick_one(main_win, label, screen, gemini_failed)
            if not success:
                failed.append(label)
            else:
                screen = capture_screen()  # refresh after panel may redraw

        if failed:
            state["error"] = (
                f"Could not tick checkbox(es): {failed}. "
                f"All 5 tiers (UIA-id, UIA-text, OCR, Gemini, Claude) exhausted."
            )
            logger.error("[Agent3] {}", state["error"])
            return state

        state["tax_boxes_handled"] = True
        logger.info("[Agent3] Tax checkboxes handled: {}", filters)

    except Exception as exc:
        state["error"] = f"handle_tax_checkboxes failed: {exc}"
        logger.error("[Agent3] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "handle_tax_checkboxes_error")
        except Exception:
            pass

    return state
