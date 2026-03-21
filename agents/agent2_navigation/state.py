"""State definition for Agent 2: Navigation."""

from typing import Any, TypedDict


class NavigationState(TypedDict, total=False):
    """State for the navigation agent sub-graph."""

    # Shared
    error: str | None
    app_handle: Any

    # Navigation steps
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
