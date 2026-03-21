"""Global state shared across all agents in the pipeline."""

from typing import Any, TypedDict


class GlobalState(TypedDict, total=False):
    """Full pipeline state passed through all agents.

    Uses total=False so keys can be absent initially.
    """

    # Pipeline control
    current_agent: str
    pipeline_status: str  # "running" | "success" | "failed"
    error: str | None
    app_handle: Any  # pywinauto Application, shared by all agents

    # Agent 1: Login
    app_launched: bool
    login_screen_ready: bool
    credentials_typed: bool
    connect_pressed: bool
    pre_popups_cleared: bool
    fullscreen_ready: bool
    post_popup_cleared: bool
    home_screen_ready: bool

    # Agent 2: Navigation
    report_key: str
    module: str
    folders: list[str]
    report_name: str
    filters: list[str]
    search_typed: bool
    ui_candidates: list[dict]
    exact_match: dict | None
    visual_confirmed: bool
    file_opened: bool

    # Agent 3: Filter
    filter_window_open: bool
    tax_boxes_handled: bool
    date_range_set: bool
    from_date: str
    to_date: str
    report_generated: bool

    # Agent 4: Download
    xlsx_clicked: bool
    hyperlinks_unchecked: bool
    export_ok_pressed: bool
    filename_built: str | None
    file_saved: bool
    export_popup_closed: bool
    app_quit: bool
