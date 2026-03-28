"""Main entry point for the Excellon RPA System.

Usage:
    python main.py --run          Run full pipeline directly
    python main.py --api          Start FastAPI server
    python main.py --agent login  Run a single agent
"""

import argparse
import sys
import time
from pathlib import Path

from loguru import logger

from config.settings import settings


def _setup_logging() -> None:
    """Configure loguru logging."""
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
    )
    logger.add(
        str(log_dir / "agent.log"),
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
        rotation="10 MB",
        retention="7 days",
    )


def run_full_pipeline(
    report_key: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> None:
    """Run the complete 4-agent pipeline."""
    from config.report_loader import get_active_report
    from orchestrator.graph import build_orchestrator_graph
    from orchestrator.state import GlobalState

    rk = report_key or settings.report_key
    report = get_active_report(rk)

    state: GlobalState = {
        "current_agent": "",
        "pipeline_status": "running",
        "error": None,
        "app_handle": None,
        # Agent 1
        "app_launched": False,
        "login_screen_ready": False,
        "credentials_typed": False,
        "connect_pressed": False,
        "pre_popups_cleared": False,
        "fullscreen_ready": False,
        "post_popup_cleared": False,
        "home_screen_ready": False,
        # Agent 2
        "report_key": rk,
        "module": report["module"],
        "folders": report["folders"],
        "report_name": report["report_name"],
        "filters": report["filters"],
        "search_typed": False,
        "ui_candidates": [],
        "exact_match": None,
        "visual_confirmed": False,
        "file_opened": False,
        # Agent 3
        "filter_window_open": False,
        "tax_boxes_handled": False,
        "date_range_set": False,
        "from_date": from_date or settings.filter_from_date,
        "to_date": to_date or settings.filter_to_date,
        "report_generated": False,
        # Agent 4
        "export_clicked": False,
        "export_popup_dismissed": False,
        "filename_built": None,
        "file_saved": False,
        "open_file_declined": False,
        "app_closed": False,
    }

    logger.info("=" * 60)
    logger.info("Starting Excellon RPA Pipeline")
    logger.info("Report: {} ({})", report["report_name"], rk)
    logger.info("Date range: {} → {}", state["from_date"], state["to_date"])
    logger.info("=" * 60)

    start_time = time.time()

    graph = build_orchestrator_graph()
    compiled = graph.compile()
    final_state = compiled.invoke(state)

    duration = time.time() - start_time

    logger.info("=" * 60)
    logger.info("Pipeline Status: {}", final_state.get("pipeline_status", "unknown"))
    if final_state.get("filename_built"):
        logger.info("File Saved: {}", final_state["filename_built"])
    if final_state.get("error"):
        logger.error("Error: {}", final_state["error"])
    logger.info("Duration: {:.1f}s", duration)
    logger.info("=" * 60)


def run_single_agent(agent_name: str) -> None:
    """Run a single agent by name."""
    from config.report_loader import get_active_report
    from orchestrator.state import GlobalState

    rk = settings.report_key
    report = get_active_report(rk)

    state: GlobalState = {
        "current_agent": agent_name,
        "pipeline_status": "running",
        "error": None,
        "app_handle": None,
        "app_launched": False,
        "login_screen_ready": False,
        "credentials_typed": False,
        "connect_pressed": False,
        "pre_popups_cleared": False,
        "fullscreen_ready": False,
        "post_popup_cleared": False,
        "home_screen_ready": False,
        "report_key": rk,
        "module": report["module"],
        "folders": report["folders"],
        "report_name": report["report_name"],
        "filters": report["filters"],
        "search_typed": False,
        "ui_candidates": [],
        "exact_match": None,
        "visual_confirmed": False,
        "file_opened": False,
        "filter_window_open": False,
        "tax_boxes_handled": False,
        "date_range_set": False,
        "from_date": settings.filter_from_date,
        "to_date": settings.filter_to_date,
        "report_generated": False,
        "export_clicked": False,
        "export_popup_dismissed": False,
        "filename_built": None,
        "file_saved": False,
        "open_file_declined": False,
        "app_closed": False,
    }

    # For non-login agents, connect to the already-running Excellon app
    if agent_name != "login":
        from automation.window_manager import is_app_running, connect_to_app, focus_window
        window_title = settings.app_window_title
        if is_app_running(window_title):
            app = connect_to_app(window_title)
            state["app_handle"] = app
            state["app_launched"] = True
            try:
                focus_window(app, window_title)
            except Exception:
                pass
            logger.info("Connected to running Excellon app for agent '{}'", agent_name)
        else:
            logger.error("Excellon app is not running. Start it first or run the login agent.")
            sys.exit(1)

    logger.info("Running single agent: {}", agent_name)

    if agent_name == "login":
        from agents.agent1_login.graph import build_login_graph
        graph = build_login_graph()
    elif agent_name == "navigation":
        from agents.agent2_navigation.graph import build_navigation_graph
        graph = build_navigation_graph()
    elif agent_name == "filter":
        from agents.agent3_filter.graph import build_filter_graph
        graph = build_filter_graph()
    elif agent_name == "download":
        from agents.agent4_download.graph import build_download_graph
        graph = build_download_graph()
    else:
        logger.error("Unknown agent: '{}'. Valid: login, navigation, filter, download", agent_name)
        sys.exit(1)

    compiled = graph.compile()
    final_state = compiled.invoke(state)

    if final_state.get("error"):
        logger.error("Agent '{}' failed: {}", agent_name, final_state["error"])
    else:
        logger.info("Agent '{}' completed successfully.", agent_name)


def start_api_server() -> None:
    """Start the FastAPI server with uvicorn."""
    import uvicorn

    logger.info("Starting API server on {}:{}", settings.api_host, settings.api_port)
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate mode."""
    _setup_logging()

    parser = argparse.ArgumentParser(
        description="Excellon RPA System — Multi-agent automation pipeline",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--run",
        action="store_true",
        help="Run the full pipeline directly",
    )
    group.add_argument(
        "--api",
        action="store_true",
        help="Start the FastAPI server",
    )
    group.add_argument(
        "--agent",
        type=str,
        choices=["login", "navigation", "filter", "download"],
        help="Run a single agent",
    )

    # Optional overrides for --run mode
    parser.add_argument("--report-key", type=str, default=None, help="Override report key")
    parser.add_argument("--from-date", type=str, default=None, help="Override from date")
    parser.add_argument("--to-date", type=str, default=None, help="Override to date")

    args = parser.parse_args()

    if args.run:
        run_full_pipeline(
            report_key=args.report_key,
            from_date=args.from_date,
            to_date=args.to_date,
        )
    elif args.api:
        start_api_server()
    elif args.agent:
        run_single_agent(args.agent)


if __name__ == "__main__":
    main()
