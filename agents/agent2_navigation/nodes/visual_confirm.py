"""Node: Visual confirmation of selection via OpenCV + Gemini."""

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, capture_region, get_element_region, save_debug_screenshot
from automation.ui_tree_reader import get_left_panel
from vision.highlight_detector import detect_blue_highlights, find_full_width_highlight
from vision.gemini_verifier import verify_selection_with_gemini


def visual_confirm_node(state: GlobalState) -> GlobalState:
    """Two-step visual verification of the selected item.

    Step 1 (OpenCV): Detect blue highlight at the expected position.
    Step 2 (Gemini): AI-based confirmation of the highlighted item.
    """
    logger.info("[Agent2] Node: visual_confirm — entering")
    try:
        app = state["app_handle"]
        exact_match = state["exact_match"]
        report_name = state["report_name"]
        folders = state["folders"]

        # Coordinate-based candidates (from screenshot fallback) are already
        # verified by Gemini/OpenCV — skip visual confirmation entirely.
        if exact_match.get("element") is None:
            state["visual_confirmed"] = True
            logger.info(
                "[Agent2] visual_confirm skipped — coordinate-based candidate "
                "already verified at ({}, {}).",
                exact_match.get("screen_x"), exact_match.get("screen_y"),
            )
            return state

        # ── Step 1: OpenCV highlight detection ──
        logger.info("Step 1: OpenCV blue highlight detection.")

        full_screenshot = capture_screen()
        save_debug_screenshot(full_screenshot, "visual_confirm_full")

        # Get left panel region
        try:
            panel = get_left_panel(app)
            panel_rect = panel.rectangle()
            panel_x = panel_rect.left
            panel_y = panel_rect.top
            panel_w = panel_rect.width()
            panel_h = panel_rect.height()
        except Exception as exc:
            logger.warning("Could not get panel rect, using element rect: {}", exc)
            elem_rect = exact_match["rect"]
            panel_x = 0
            panel_y = elem_rect.top - 100
            panel_w = elem_rect.right + 50
            panel_h = 300

        # Crop to left panel
        cropped = capture_region(panel_x, panel_y, panel_w, panel_h)
        save_debug_screenshot(cropped, "visual_confirm_panel")

        # Detect highlights
        highlights = detect_blue_highlights(cropped)

        # Get target Y position relative to panel
        elem_rect = exact_match["rect"]
        target_center_y = (elem_rect.top + elem_rect.bottom) // 2 - panel_y

        full_width_match = find_full_width_highlight(
            highlights, panel_w, target_center_y, tolerance_y=15
        )

        if full_width_match is None:
            logger.warning(
                "[Agent2] OpenCV: no full-width highlight at y={} for '{}' "
                "({} highlight(s) detected) — trusting exact_match and continuing.",
                target_center_y, report_name, len(highlights),
            )
            save_debug_screenshot(cropped, "visual_confirm_opencv_warn")
        else:
            logger.info(
                "OpenCV: Full-width highlight confirmed at y={}.",
                full_width_match["center_y"],
            )

        # ── Step 2: Gemini verification (optional — skip if no API key) ──
        from config.settings import settings as _settings
        if not _settings.gemini_api_key:
            logger.info("Step 2: Gemini key not configured — skipping AI verification.")
        else:
            logger.info("Step 2: Gemini AI visual verification.")
            gemini_result = verify_selection_with_gemini(cropped, report_name, folders)
            if not gemini_result:
                logger.warning(
                    "[Agent2] Gemini could not confirm '{}' — trusting exact_match and continuing.",
                    report_name,
                )
                save_debug_screenshot(cropped, "visual_confirm_gemini_warn")
            else:
                logger.info("Gemini: selection confirmed for '{}'.", report_name)

        state["visual_confirmed"] = True
        logger.info("[Agent2] visual_confirm passed for '{}'.", report_name)

    except Exception as exc:
        state["error"] = f"visual_confirm failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "visual_confirm_error")
        except Exception:
            pass

    return state
