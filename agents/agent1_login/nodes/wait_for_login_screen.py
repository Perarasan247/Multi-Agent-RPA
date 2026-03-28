"""Node: Wait for login screen to appear with username/password fields."""

import time

import pygetwindow as gw
from loguru import logger
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_element_info import UIAElementInfo

from orchestrator.state import GlobalState
from automation.window_manager import _is_excellon_window
from automation.screenshot import capture_screen, save_debug_screenshot
from config.settings import settings


def _get_excellon_uia_wrapper():
    """Get a UIA wrapper for the Excellon window by its HWND.

    Uses pygetwindow for fast HWND lookup, then wraps with UIA directly.
    This avoids the slow app.windows() / app.top_window() tree walk.
    """
    for w in gw.getAllWindows():
        if w.title and _is_excellon_window(w.title, settings.app_window_title):
            try:
                return UIAWrapper(UIAElementInfo(w._hWnd)), w.title
            except Exception:
                continue
    return None, None


def _check_for_login(wrapper):
    """Check if the UIA wrapper has login fields (Edit + Connect button).

    Returns (edit_count, connect_found, wrapper_with_edits).
    """
    edit_count = 0
    connect_found = False

    try:
        for d in wrapper.descendants():
            try:
                ct = d.element_info.control_type
                if ct == "Edit":
                    edit_count += 1
                elif ct == "Button":
                    txt = (d.window_text() or "").strip().lower()
                    if "connect" in txt:
                        connect_found = True
            except Exception:
                continue
    except Exception:
        pass

    return edit_count, connect_found


def wait_for_login_screen_node(state: GlobalState) -> GlobalState:
    """Poll until the login screen with credential fields is visible."""
    logger.info("[Agent1] Node: wait_for_login_screen — entering")
    try:
        timeout = 15
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            wrapper, title = _get_excellon_uia_wrapper()
            if wrapper is None:
                time.sleep(0.5)
                continue

            edit_count, connect_found = _check_for_login(wrapper)
            logger.debug("[Agent1] Window '{}': edits={}, connect={}",
                         title, edit_count, connect_found)

            if edit_count >= 2 and connect_found:
                state["login_screen_ready"] = True
                logger.info(
                    "[Agent1] Login screen ready: {} edit fields, "
                    "Connect button found in '{}'.",
                    edit_count, title,
                )
                return state

            # If window has version in title but no login fields → already logged in
            import re
            if re.search(r"Excellon\s+\d+\.\d+", title or "", re.IGNORECASE):
                if not connect_found:
                    state["login_screen_ready"] = True
                    state["already_logged_in"] = True
                    logger.info(
                        "[Agent1] Already logged in — '{}' has version, no Connect button.",
                        title,
                    )
                    return state

            time.sleep(0.5)

        # Timeout — check if already logged in (no Connect button)
        wrapper, title = _get_excellon_uia_wrapper()
        if wrapper is not None:
            edit_count, connect_found = _check_for_login(wrapper)
            if not connect_found and edit_count == 0:
                state["login_screen_ready"] = True
                state["already_logged_in"] = True
                logger.info(
                    "[Agent1] Already logged in — '{}', no login fields found.",
                    title,
                )
                return state

        state["error"] = (
            f"Login screen did not appear in {timeout}s. "
            f"Could not find username/password fields and Connect button."
        )
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "login_screen_timeout")
        except Exception:
            pass

    except Exception as exc:
        state["error"] = f"wait_for_login_screen failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "login_screen_error")
        except Exception:
            pass

    return state
