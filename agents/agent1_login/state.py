"""State definition for Agent 1: Login."""

from typing import Any, TypedDict


class LoginState(TypedDict, total=False):
    """State for the login agent sub-graph."""

    # Shared
    error: str | None
    app_handle: Any

    # Login steps
    app_launched: bool
    login_screen_ready: bool
    credentials_typed: bool
    connect_pressed: bool
    pre_popups_cleared: bool
    fullscreen_ready: bool
    post_popup_cleared: bool
    home_screen_ready: bool
