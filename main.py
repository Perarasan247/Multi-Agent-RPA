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

from config.license import check_license
from config.settings import settings


def _validate_license() -> None:
    license_path = Path.cwd() / "license.key"
    check_license(settings.license_secret, license_path)


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


MAX_RETRIES = 3


def _build_fresh_state(
    rk: str, report: dict,
    from_date: str | None, to_date: str | None,
):
    """Build a fresh GlobalState for a pipeline run."""
    from orchestrator.state import GlobalState
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
        "skip_filters": report["skip_filters"],
        "as_on_date_only": report["as_on_date_only"],
        "dealer": report["dealer"],
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
    return state


def _verify_downloaded_file(final_state: dict) -> bool:
    """Check the downloaded file actually exists on disk."""
    from pathlib import Path

    filename = final_state.get("filename_built")
    if not filename:
        logger.error("[Verify] No filename was built — cannot verify.")
        return False

    save_dir = settings.save_path
    full_path = Path(save_dir) / filename

    if full_path.exists():
        size_kb = full_path.stat().st_size / 1024
        logger.info("[Verify] File confirmed: '{}' ({:.1f} KB)", full_path, size_kb)
        return True
    else:
        logger.error("[Verify] File NOT found at: '{}'", full_path)
        return False


def run_full_pipeline(
    report_key: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> bool:
    """Run the complete 4-agent pipeline with retry on failure.

    Returns True on success, False if all retries are exhausted.
    """
    from config.report_loader import get_active_report
    from orchestrator.graph import build_orchestrator_graph

    rk = report_key or settings.report_key
    report = get_active_report(rk)

    for attempt in range(1, MAX_RETRIES + 1):
        state = _build_fresh_state(rk, report, from_date, to_date)

        logger.info("=" * 60)
        logger.info("Starting Excellon RPA Pipeline (attempt {}/{})", attempt, MAX_RETRIES)
        logger.info("Report: {} ({})", report["report_name"], rk)
        logger.info("Date range: {} → {}", state["from_date"], state["to_date"])
        logger.info("=" * 60)

        start_time = time.time()

        graph = build_orchestrator_graph()
        compiled = graph.compile()
        final_state = compiled.invoke(state)

        duration = time.time() - start_time

        # Check if pipeline succeeded
        if final_state.get("pipeline_status") == "success":
            # Verify the file was actually downloaded
            if _verify_downloaded_file(final_state):
                logger.info("=" * 60)
                logger.info("Pipeline Status: SUCCESS")
                logger.info("File Saved: {}", final_state["filename_built"])
                logger.info("Duration: {:.1f}s", duration)
                logger.info("=" * 60)
                return True
            else:
                logger.error(
                    "Pipeline reported success but file not found on disk. "
                    "Attempt {}/{} failed.",
                    attempt, MAX_RETRIES,
                )
        else:
            logger.error(
                "Pipeline failed: {} | Attempt {}/{}",
                final_state.get("error", "Unknown error"),
                attempt, MAX_RETRIES,
            )

        # If not the last attempt, ensure Excellon is gone before retrying
        if attempt < MAX_RETRIES:
            try:
                from automation.window_manager import is_app_running
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if not is_app_running(settings.app_window_title):
                        break
                    time.sleep(1.0)
                else:
                    logger.warning("Excellon still running before retry — proceeding anyway.")
            except Exception:
                pass
            logger.info("Waiting 5 seconds before retry...")
            time.sleep(5)

    # All retries exhausted
    logger.error("=" * 60)
    logger.error("Pipeline FAILED after {} attempts.", MAX_RETRIES)
    logger.error("Report: {} ({})", report["report_name"], rk)
    logger.error("Last error: {}", final_state.get("error", "Unknown"))
    logger.error("=" * 60)
    return False


def run_all_reports(
    report_keys: list[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> None:
    """Run every report in reports.json sequentially.

    Args:
        report_keys: Explicit list of keys to run. If None, runs all keys in
                     reports.json in order.
        from_date:   Override from date for all reports.
        to_date:     Override to date (also used as as-on-date for stock reports).
    """
    from config.report_loader import get_all_report_keys

    keys = report_keys or get_all_report_keys()
    total = len(keys)
    results: dict[str, str] = {}

    logger.info("=" * 60)
    logger.info("BATCH: Starting {} report(s).", total)
    logger.info("=" * 60)

    for i, key in enumerate(keys, 1):
        logger.info("BATCH [{}/{}]: {}", i, total, key)
        try:
            success = run_full_pipeline(key, from_date, to_date)
            results[key] = "SUCCESS" if success else "FAILED"
        except Exception as exc:
            logger.error("BATCH: '{}' raised unexpected exception: {}", key, exc)
            results[key] = f"ERROR: {exc}"

        # Brief pause between reports so Excellon has time to fully close
        if i < total:
            time.sleep(3)

    # ── Summary ──────────────────────────────────────────────────────────────
    succeeded = [k for k, v in results.items() if v == "SUCCESS"]
    failed    = [k for k, v in results.items() if v != "SUCCESS"]

    logger.info("=" * 60)
    logger.info("BATCH COMPLETE: {}/{} succeeded.", len(succeeded), total)
    for key, status in results.items():
        marker = "✓" if status == "SUCCESS" else "✗"
        logger.info("  {} {} → {}", marker, key, status)
    logger.info("=" * 60)

    if failed:
        logger.error("BATCH: Failed reports: {}", failed)


def run_single_agent(
    agent_name: str,
    report_key: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> None:
    """Run a single agent by name.

    Args:
        agent_name: 'login', 'navigation', 'filter', or 'download'.
        report_key: Override report key (defaults to settings.report_key).
        from_date: Override from date (defaults to settings.filter_from_date).
        to_date: Override to date (defaults to settings.filter_to_date).
    """
    from config.report_loader import get_active_report
    from orchestrator.state import GlobalState

    rk = report_key or settings.report_key
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
        "skip_filters": report["skip_filters"],
        "as_on_date_only": report["as_on_date_only"],
        "dealer": report["dealer"],
        "search_typed": False,
        "ui_candidates": [],
        "exact_match": None,
        "visual_confirmed": False,
        "file_opened": False,
        "filter_window_open": False,
        "tax_boxes_handled": False,
        "date_range_set": False,
        "from_date": from_date or settings.filter_from_date,
        "to_date": to_date or settings.filter_to_date,
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
    _validate_license()

    parser = argparse.ArgumentParser(
        description="Excellon RPA System — Multi-agent automation pipeline",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--run",
        action="store_true",
        help="Run the full pipeline for a single report",
    )
    group.add_argument(
        "--run-all",
        action="store_true",
        help="Run every report in reports.json sequentially",
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

    # Optional overrides
    parser.add_argument("--report-key", type=str, default=None, help="Override report key (--run only)")
    parser.add_argument(
        "--reports",
        type=str,
        default=None,
        help="Comma-separated report keys to run (--run-all only, e.g. sale_statement,stock_valuation)",
    )
    parser.add_argument("--from-date", type=str, default=None, help="Override from date (DD/MM/YYYY)")
    parser.add_argument("--to-date", type=str, default=None, help="Override to date (DD/MM/YYYY)")

    args = parser.parse_args()

    if args.run:
        run_full_pipeline(
            report_key=args.report_key,
            from_date=args.from_date,
            to_date=args.to_date,
        )
    elif args.run_all:
        keys = [k.strip() for k in args.reports.split(",")] if args.reports else None
        run_all_reports(
            report_keys=keys,
            from_date=args.from_date,
            to_date=args.to_date,
        )
    elif args.api:
        start_api_server()
    elif args.agent:
        run_single_agent(args.agent)


if __name__ == "__main__":
    main()
