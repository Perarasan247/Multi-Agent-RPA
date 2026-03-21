"""Node: Type username and password into login fields."""

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.keyboard_mouse import clear_field, type_text_slow
from automation.screenshot import capture_screen, save_debug_screenshot


def type_credentials_node(state: GlobalState) -> GlobalState:
    """Type username and password into the login form.

    Finds the first two Edit controls and types credentials.
    Password value is NEVER logged.
    """
    logger.info("[Agent1] Node: type_credentials — entering")
    try:
        app = state["app_handle"]
        main_win = app.top_window()
        edits = main_win.descendants(control_type="Edit")

        if len(edits) < 2:
            state["error"] = (
                f"Expected at least 2 Edit fields for credentials, found {len(edits)}."
            )
            logger.error("[Agent1] {}", state["error"])
            return state

        # Username field (first Edit)
        username_field = None
        password_field = None

        for edit in edits:
            try:
                name = (edit.element_info.name or "").lower()
                auto_id = (edit.element_info.automation_id or "").lower()
                if "user" in name or "user" in auto_id or "login" in name:
                    username_field = edit
                elif "pass" in name or "pass" in auto_id:
                    password_field = edit
            except Exception:
                continue

        # Fallback: use positional order
        if username_field is None:
            username_field = edits[0]
        if password_field is None:
            password_field = edits[1] if len(edits) > 1 else edits[0]

        # Type username
        logger.info("Typing username: '{}'", settings.excellon_username)
        clear_field(username_field)
        type_text_slow(username_field, settings.excellon_username, delay=0.05)

        # Type password (NEVER log the value)
        logger.info("Typing password: ****")
        clear_field(password_field)
        type_text_slow(password_field, settings.excellon_password, delay=0.05)

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
