"""Node: Build the output filename based on report metadata."""

import re
import time

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings


def build_filename_node(state: GlobalState) -> GlobalState:
    """Construct a descriptive filename for the exported report.

    Format: {dealer_code}_{branch_code}_{report_key}_{from}_{to}_{timestamp}.xlsx
    All spaces replaced with underscores, special chars removed.
    """
    logger.info("[Agent4] Node: build_filename — entering")
    try:
        dealer_code = settings.dealer_code
        branch_code = settings.branch_code
        report_key = state.get("report_key", settings.report_key)
        from_date = state.get("from_date", settings.filter_from_date)
        to_date = state.get("to_date", settings.filter_to_date)

        # Clean date strings: replace / with -
        from_clean = from_date.replace("/", "-")
        to_clean = to_date.replace("/", "-")

        # Build timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Assemble filename
        raw_name = (
            f"{dealer_code}_{branch_code}_{report_key}_"
            f"{from_clean}_to_{to_clean}_{timestamp}"
        )

        # Sanitize: remove special chars, replace spaces with underscores
        clean_name = raw_name.replace(" ", "_")
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", clean_name)

        filename = f"{clean_name}.xlsx"

        state["filename_built"] = filename
        logger.info("[Agent4] Filename built: {}", filename)

    except Exception as exc:
        state["error"] = f"build_filename failed: {exc}"
        logger.error("[Agent4] {}", state["error"])

    return state
