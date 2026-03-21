"""State definition for Agent 3: Filter."""

from typing import Any, TypedDict


class FilterState(TypedDict, total=False):
    """State for the filter agent sub-graph."""

    # Shared
    error: str | None
    app_handle: Any

    # From Agent 2 (carried forward)
    filters: list[str]

    # Filter steps
    filter_window_open: bool
    tax_boxes_handled: bool
    date_range_set: bool
    from_date: str
    to_date: str
    report_generated: bool
