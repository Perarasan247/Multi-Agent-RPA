"""Node: Read report configuration from reports.json."""

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from config.report_loader import get_active_report


def read_config_node(state: GlobalState) -> GlobalState:
    """Load report configuration into state.

    Reads report_key from settings, looks up the report definition,
    and populates module, folders, report_name, and filters.
    """
    logger.info("[Agent2] Node: read_config — entering")
    try:
        report_key = state.get("report_key") or settings.report_key
        report = get_active_report(report_key)

        state["report_key"] = report_key
        state["module"] = report["module"]
        state["folders"] = report["folders"]
        state["report_name"] = report["report_name"]
        state["filters"] = report["filters"]

        logger.info(
            "[Agent2] Report config loaded: '{}' in {} > {}",
            report["report_name"],
            report["module"],
            " > ".join(report["folders"]),
        )

    except Exception as exc:
        state["error"] = f"read_config failed: {exc}"
        logger.error("[Agent2] {}", state["error"])

    return state
