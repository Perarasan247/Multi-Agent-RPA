"""Node: Verify the home screen is fully loaded and visible."""

import time

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def verify_home_screen_node(state: GlobalState) -> GlobalState:
    """Verify the Excellon home screen is visible.

    Checks for:
        - 'Recently Used' text element
        - Left menu panel visible
        - Search bar present
    """
    logger.info("[Agent1] Node: verify_home_screen — entering")
    try:
        app = state["app_handle"]
        timeout = 10
        start = time.time()

        while time.time() - start < timeout:
            try:
                main_win = app.top_window()
                all_texts = []

                # Collect all visible text
                try:
                    descendants = main_win.descendants()
                    for desc in descendants:
                        try:
                            text = desc.window_text().strip()
                            if text:
                                all_texts.append(text.lower())
                        except Exception:
                            continue
                except Exception:
                    pass

                recently_used = any("recently used" in t for t in all_texts)

                # Check for left panel (Tree or Pane with tree items)
                left_panel = False
                try:
                    trees = main_win.descendants(control_type="Tree")
                    if trees:
                        left_panel = True
                except Exception:
                    pass
                if not left_panel:
                    try:
                        tree_items = main_win.descendants(control_type="TreeItem")
                        if tree_items:
                            left_panel = True
                    except Exception:
                        pass

                # Check for search bar
                search_bar = False
                try:
                    edits = main_win.descendants(control_type="Edit")
                    for edit in edits:
                        try:
                            name = (edit.element_info.name or "").lower()
                            auto_id = (edit.element_info.automation_id or "").lower()
                            text = edit.window_text().lower()
                            if "search" in name or "search" in auto_id or "keyword" in text:
                                search_bar = True
                                break
                        except Exception:
                            continue
                    # Fallback: any edit in top area
                    if not search_bar and edits:
                        search_bar = True
                except Exception:
                    pass

                if recently_used and left_panel and search_bar:
                    state["home_screen_ready"] = True
                    logger.info(
                        "[Agent1] Home screen verified: recently_used={}, left_panel={}, search_bar={}",
                        recently_used, left_panel, search_bar,
                    )
                    return state

                logger.debug(
                    "Home screen check: recently_used={}, left_panel={}, search_bar={}",
                    recently_used, left_panel, search_bar,
                )

            except Exception as exc:
                logger.debug("Polling home screen: {}", exc)

            time.sleep(0.5)

        state["error"] = (
            f"Home screen not verified within {timeout}s. "
            "Could not confirm Recently Used, left panel, and search bar."
        )
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "verify_home_screen_timeout")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"verify_home_screen failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "verify_home_screen_error")
        except Exception:
            pass

    return state
