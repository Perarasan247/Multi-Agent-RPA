"""Node: Type username and password into login fields."""

import time

import pyautogui
import pygetwindow as gw
from loguru import logger
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_element_info import UIAElementInfo

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import _is_excellon_window
from automation.screenshot import capture_screen, save_debug_screenshot

pyautogui.FAILSAFE = False


def _get_excellon_uia_wrapper():
    """Get a UIA wrapper for the Excellon window by HWND (fast)."""
    for w in gw.getAllWindows():
        if w.title and _is_excellon_window(w.title, settings.app_window_title):
            try:
                return UIAWrapper(UIAElementInfo(w._hWnd))
            except Exception:
                continue
    return None


def _find_login_fields(wrapper):
    """Find the User Name and Password edit fields by their labels.

    The login form has: Server (ComboBox+Edit), User Name (Edit), Password (Edit).
    We identify them by checking the nearby label text or automation properties.
    Returns (username_edit, password_edit) or (None, None).
    """
    edits = []
    for d in wrapper.descendants():
        try:
            if d.element_info.control_type == "Edit":
                name = (d.element_info.name or "").lower()
                auto_id = (d.element_info.automation_id or "").lower()
                edits.append((d, name, auto_id))
        except Exception:
            continue

    username_field = None
    password_field = None

    for edit, name, auto_id in edits:
        if "user" in name or "user" in auto_id or "login" in name:
            username_field = edit
        elif "pass" in name or "pass" in auto_id:
            password_field = edit

    # If label-based matching fails, use positional order but skip
    # the Server ComboBox Edit (which typically contains a URL like "https://")
    if username_field is None or password_field is None:
        non_server_edits = []
        for edit, name, auto_id in edits:
            try:
                val = (edit.get_value() or edit.window_text() or "").strip()
            except Exception:
                val = ""
            # Skip edits that look like the Server URL field
            if "http" in val.lower() or "server" in name or "server" in auto_id:
                continue
            non_server_edits.append(edit)

        if len(non_server_edits) >= 2:
            if username_field is None:
                username_field = non_server_edits[0]
            if password_field is None:
                password_field = non_server_edits[1]
        elif len(non_server_edits) == 1:
            if username_field is None:
                username_field = non_server_edits[0]

    return username_field, password_field


def _type_into_field(field, text: str):
    """Click the field and type text safely using pyautogui at the field's location."""
    r = field.rectangle()
    cx, cy = r.mid_point().x, r.mid_point().y

    # Click directly at the field center (avoids mis-clicking nearby elements)
    pyautogui.click(cx, cy)
    time.sleep(0.2)

    # Select all and delete existing content
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)

    # Type the text
    field.type_keys(text, with_spaces=True, pause=0.05)
    time.sleep(0.2)


def type_credentials_node(state: GlobalState) -> GlobalState:
    """Type username and password into the login form."""
    logger.info("[Agent1] Node: type_credentials — entering")
    try:
        wrapper = _get_excellon_uia_wrapper()
        if wrapper is None:
            state["error"] = "Cannot find Excellon window for typing credentials."
            logger.error("[Agent1] {}", state["error"])
            return state

        username_field, password_field = _find_login_fields(wrapper)

        if username_field is None or password_field is None:
            state["error"] = (
                f"Could not identify login fields. "
                f"username={'found' if username_field else 'missing'}, "
                f"password={'found' if password_field else 'missing'}"
            )
            logger.error("[Agent1] {}", state["error"])
            return state

        logger.info("[Agent1] Found login fields: username='{}', password='{}'",
                     username_field.element_info.name,
                     password_field.element_info.name)

        # Type username
        logger.info("Typing username: '{}'", settings.excellon_username)
        _type_into_field(username_field, settings.excellon_username)

        # Type password (NEVER log the value)
        logger.info("Typing password: ****")
        _type_into_field(password_field, settings.excellon_password)

        state["credentials_typed"] = True
        logger.info("[Agent1] Node: type_credentials — completed successfully")

    except Exception as exc:
        state["error"] = f"type_credentials failed: {exc}"
        logger.error("[Agent1] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "type_credentials_error")
        except Exception:
            pass

    return state
