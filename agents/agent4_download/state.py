"""State definition for Agent 4: Download."""

from typing import Any, TypedDict


class DownloadState(TypedDict, total=False):
    """State for the download agent sub-graph."""

    # Shared
    error: str | None
    app_handle: Any

    # From earlier agents (carried forward)
    report_key: str
    report_name: str
    from_date: str
    to_date: str

    # Download steps
    xlsx_clicked: bool
    hyperlinks_unchecked: bool
    export_ok_pressed: bool
    filename_built: str | None
    file_saved: bool
    export_popup_closed: bool
    app_quit: bool
