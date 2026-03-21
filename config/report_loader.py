"""Load report definitions from reports.json."""

import json
from pathlib import Path
from loguru import logger

_REPORTS_PATH = Path(__file__).resolve().parent.parent / "reports.json"


def _load_reports() -> dict:
    """Load the full reports.json file and return as dict."""
    with open(_REPORTS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def get_active_report(report_key: str) -> dict:
    """Look up a report definition by key.

    Returns dict with keys: module, folders, report_name, filters.
    Raises ValueError if report_key is not found.
    """
    reports = _load_reports()
    if report_key not in reports:
        available = list(reports.keys())
        raise ValueError(
            f"Report key '{report_key}' not found. "
            f"Available keys: {available}"
        )
    entry = reports[report_key]
    result = {
        "module": entry["module"],
        "folders": entry["folders"],
        "report_name": entry["report_name"],
        "filters": entry.get("filters", []),
    }
    logger.info(
        "Loaded report config: {} in {} > {}",
        result["report_name"],
        result["module"],
        " > ".join(result["folders"]),
    )
    return result


def get_filters(report_key: str) -> list[str]:
    """Return the filters list for a report, or empty list if none."""
    reports = _load_reports()
    if report_key not in reports:
        return []
    return reports[report_key].get("filters", [])
