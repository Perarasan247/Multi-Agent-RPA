"""Node: Click the module on the left-side navigation menu.

Three-tier fallback chain:
  1. UIA descendants — fast, free, works most of the time.
  2. OCR (RapidOCR)  — when UIA picks the wrong control (text fragments
                       inside other menu items, stale tree, etc.).
  3. Claude Haiku    — when OCR fails (low confidence, missing model,
                       offline scenarios).

Each tier:
  - Locates the module's screen coordinates.
  - Clicks at that location.
  - Verifies expansion by checking that the left-panel item count grew
    by at least _MIN_NEW_ITEMS. If verification fails, the next tier
    is attempted.
"""

import time
from typing import Optional, Tuple

import pyautogui
from loguru import logger

from orchestrator.state import GlobalState
from automation.window_manager import get_main_window
from automation.screenshot import capture_screen, save_debug_screenshot


# Left panel width (pixels) — controls beyond this are not menu items
_LEFT_PANEL_WIDTH = 280

# Menu items live below the title bar + ribbon + toolbar + search bar.
_MENU_MIN_TOP_OFFSET = 200

# Timeout & poll cadence for expansion verification
_EXPANSION_TIMEOUT_SEC = 8.0
_EXPANSION_POLL_INTERVAL_SEC = 0.4

# Minimum item-count delta that counts as expansion / collapse
_MIN_NEW_ITEMS = 2


# ── Helpers for left-panel item enumeration / counting ──────────────────


def _iter_left_panel_text_controls(main_win, max_x: int, min_y: int):
    try:
        for ctrl in main_win.descendants():
            try:
                text = (ctrl.window_text() or "").strip()
                if not text:
                    continue
                rect = ctrl.rectangle()
                if rect.left > max_x or rect.top < min_y:
                    continue
                yield ctrl, text, rect
            except Exception:
                continue
    except Exception as exc:
        logger.debug("[Agent2] descendants() error: {}", exc)


def _find_left_panel_controls_by_text(main_win, target_text: str,
                                      max_x: int, min_y: int) -> list:
    target = target_text.strip().lower()
    matches = []
    for ctrl, text, rect in _iter_left_panel_text_controls(main_win, max_x, min_y):
        if text.lower() == target:
            matches.append((ctrl, rect.top))
    matches.sort(key=lambda x: x[1])
    return matches


def _is_subfolder_visible(main_win, subfolder: str,
                          max_x: int, min_y: int) -> bool:
    target = subfolder.strip().lower()
    for _, text, _ in _iter_left_panel_text_controls(main_win, max_x, min_y):
        if target in text.lower():
            return True
    return False


def _count_left_panel_items(main_win, max_x: int, min_y: int) -> int:
    return sum(1 for _ in _iter_left_panel_text_controls(main_win, max_x, min_y))


def _snapshot_left_panel_text(main_win, max_x: int, min_y: int,
                              limit: int = 40) -> list[str]:
    rows = []
    for _, text, rect in _iter_left_panel_text_controls(main_win, max_x, min_y):
        rows.append(f"  y={rect.top:<5} x={rect.left:<5} '{text}'")
        if len(rows) >= limit:
            rows.append(f"  ... (truncated at {limit})")
            break
    return rows


def _wait_for_growth(main_win, max_x: int, min_y: int,
                     baseline: int, timeout: float) -> Tuple[bool, int]:
    """Poll until item count grows by >= _MIN_NEW_ITEMS or timeout."""
    deadline = time.time() + timeout
    final = baseline
    while time.time() < deadline:
        final = _count_left_panel_items(main_win, max_x, min_y)
        if final - baseline >= _MIN_NEW_ITEMS:
            return True, final
        time.sleep(_EXPANSION_POLL_INTERVAL_SEC)
    return False, final


# ── Each tier returns True on success, False to fall through ────────────


def _try_uia(state: GlobalState, main_win, module_name: str,
             max_x: int, min_y: int, items_before: int) -> bool:
    """Tier 1: UIA descendants → click the topmost matching control."""
    matches = _find_left_panel_controls_by_text(
        main_win, module_name, max_x, min_y,
    )
    if not matches:
        logger.info("[Agent2] UIA: no descendant matches '{}'.", module_name)
        return False

    ctrl = matches[0][0]
    try:
        ctrl.click_input()
        logger.info("[Agent2] UIA clicked module: '{}'", module_name)
    except Exception as exc:
        logger.warning("[Agent2] UIA click failed: {}", exc)
        return False

    grew, count = _wait_for_growth(
        main_win, max_x, min_y, items_before, _EXPANSION_TIMEOUT_SEC,
    )
    if grew:
        logger.info(
            "[Agent2] UIA verification passed — items {} → {}.",
            items_before, count,
        )
        return True

    # Maybe we collapsed an already-expanded menu — re-click the same control.
    if items_before - count >= _MIN_NEW_ITEMS:
        logger.info(
            "[Agent2] UIA: items shrank ({} → {}) — re-clicking to re-expand.",
            items_before, count,
        )
        try:
            ctrl.click_input()
        except Exception as exc:
            logger.warning("[Agent2] UIA re-click failed: {}", exc)
            return False
        grew_again, count_after = _wait_for_growth(
            main_win, max_x, min_y, count, _EXPANSION_TIMEOUT_SEC,
        )
        if grew_again:
            logger.info(
                "[Agent2] UIA re-click verified — items {} → {}.",
                count, count_after,
            )
            return True

    logger.warning(
        "[Agent2] UIA click did not expand the menu — falling back to OCR.",
    )
    return False


def _click_at_coords_and_verify(coords: Tuple[int, int], main_win,
                                max_x: int, min_y: int,
                                items_before: int, label: str) -> bool:
    """Click at given screen coords and verify expansion."""
    sx, sy = coords
    try:
        pyautogui.moveTo(sx, sy, duration=0.15)
        time.sleep(0.1)
        pyautogui.click(sx, sy)
        logger.info("[Agent2] {} clicked at ({}, {}).", label, sx, sy)
    except Exception as exc:
        logger.warning("[Agent2] {} click failed: {}", label, exc)
        return False

    grew, count = _wait_for_growth(
        main_win, max_x, min_y, items_before, _EXPANSION_TIMEOUT_SEC,
    )
    if grew:
        logger.info(
            "[Agent2] {} verification passed — items {} → {}.",
            label, items_before, count,
        )
        return True

    if items_before - count >= _MIN_NEW_ITEMS:
        # Already-expanded → click again
        logger.info(
            "[Agent2] {}: items shrank ({} → {}) — re-clicking.",
            label, items_before, count,
        )
        try:
            pyautogui.click(sx, sy)
        except Exception:
            return False
        grew_again, count_after = _wait_for_growth(
            main_win, max_x, min_y, count, _EXPANSION_TIMEOUT_SEC,
        )
        if grew_again:
            logger.info(
                "[Agent2] {} re-click verified — items {} → {}.",
                label, count, count_after,
            )
            return True

    logger.warning(
        "[Agent2] {} click did not expand the menu (items: {} → {}).",
        label, items_before, count,
    )
    return False


def _try_ocr(state: GlobalState, main_win, module_name: str,
             max_x: int, min_y: int, items_before: int) -> bool:
    """Tier 2: RapidOCR — find module text by reading screen pixels."""
    try:
        from vision.ocr_module_finder import find_module_via_ocr
    except Exception as exc:
        logger.warning("[Agent2] OCR import failed: {}", exc)
        return False

    win_rect = main_win.rectangle()
    panel_left = max(0, win_rect.left)
    panel_top = max(0, win_rect.top + _MENU_MIN_TOP_OFFSET)
    panel_width = _LEFT_PANEL_WIDTH
    panel_height = max(400, win_rect.height() - _MENU_MIN_TOP_OFFSET)

    try:
        screenshot = capture_screen()
    except Exception as exc:
        logger.warning("[Agent2] could not capture screen for OCR: {}", exc)
        return False

    coords = find_module_via_ocr(
        screenshot, module_name,
        panel_left, panel_top, panel_width, panel_height,
    )
    if coords is None:
        logger.info("[Agent2] OCR could not find '{}'.", module_name)
        return False

    return _click_at_coords_and_verify(
        coords, main_win, max_x, min_y, items_before, "OCR",
    )


def _try_llm(state: GlobalState, main_win, module_name: str,
             max_x: int, min_y: int, items_before: int) -> bool:
    """Tier 3: Claude Haiku vision — final fallback."""
    try:
        from vision.anthropic_verifier import anthropic_find_module
    except Exception as exc:
        logger.warning("[Agent2] LLM import failed: {}", exc)
        return False

    win_rect = main_win.rectangle()
    panel_left = max(0, win_rect.left)
    panel_top = max(0, win_rect.top + _MENU_MIN_TOP_OFFSET)
    panel_width = _LEFT_PANEL_WIDTH
    panel_height = max(400, win_rect.height() - _MENU_MIN_TOP_OFFSET)

    try:
        screenshot = capture_screen()
    except Exception as exc:
        logger.warning("[Agent2] could not capture screen for LLM: {}", exc)
        return False

    coords = anthropic_find_module(
        screenshot, module_name,
        panel_left, panel_top, panel_width, panel_height,
    )
    if coords is None:
        logger.info("[Agent2] Claude could not find '{}'.", module_name)
        return False

    return _click_at_coords_and_verify(
        coords, main_win, max_x, min_y, items_before, "Claude",
    )


# ── The node itself ─────────────────────────────────────────────────────


def click_module_node(state: GlobalState) -> GlobalState:
    """Click the module on the left navigation menu, verify expansion.

    Tries UIA → OCR → Claude vision in order. Each tier independently
    locates the module, clicks it, and verifies expansion. The first
    tier whose verification passes wins.
    """
    logger.info("[Agent2] Node: click_module — entering")
    try:
        module_name = (state.get("module") or "").strip()
        if not module_name:
            state["error"] = "click_module: 'module' is empty in state."
            logger.error("[Agent2] {}", state["error"])
            return state

        app = state["app_handle"]
        main_win = get_main_window(app)
        win_rect = main_win.rectangle()
        max_x = win_rect.left + _LEFT_PANEL_WIDTH
        min_y = win_rect.top + _MENU_MIN_TOP_OFFSET

        items_before = _count_left_panel_items(main_win, max_x, min_y)
        logger.info("[Agent2] Left-panel items before click: {}", items_before)

        # Tier 1: UIA
        if _try_uia(state, main_win, module_name, max_x, min_y, items_before):
            logger.info("[Agent2] Node: click_module — completed via UIA")
            return state

        # Re-snapshot in case UIA changed something unexpected
        items_now = _count_left_panel_items(main_win, max_x, min_y)
        logger.info(
            "[Agent2] Item count after UIA attempt: {} (was {})",
            items_now, items_before,
        )

        # Tier 2: OCR
        if _try_ocr(state, main_win, module_name, max_x, min_y, items_now):
            logger.info("[Agent2] Node: click_module — completed via OCR")
            return state

        items_now = _count_left_panel_items(main_win, max_x, min_y)

        # Tier 3: LLM
        if _try_llm(state, main_win, module_name, max_x, min_y, items_now):
            logger.info("[Agent2] Node: click_module — completed via Claude")
            return state

        # All three tiers failed — dump diagnostics
        snapshot = _snapshot_left_panel_text(main_win, max_x, min_y)
        logger.error(
            "[Agent2] Left-panel snapshot at failure ({} items):\n{}",
            len(snapshot), "\n".join(snapshot) if snapshot else "  (empty)",
        )
        state["error"] = (
            f"click_module: all fallbacks failed for module '{module_name}' "
            f"(UIA, OCR, Claude). The menu did not expand."
        )
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_module_all_failed")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"click_module failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_module_error")
        except Exception:
            pass

    return state
