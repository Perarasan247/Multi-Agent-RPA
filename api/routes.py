"""API route definitions for the Excellon RPA System."""

import time

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import (
    RunPipelineRequest,
    RunPipelineResponse,
    AgentResult,
    HealthResponse,
    StatusResponse,
)
from config.settings import settings
from config.report_loader import get_active_report
from automation.window_manager import is_app_running
from orchestrator.graph import build_orchestrator_graph
from orchestrator.state import GlobalState

router = APIRouter()

# Module-level state tracking for /status endpoint
_last_state: GlobalState = {}


def _build_initial_state(
    report_key: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> GlobalState:
    """Build the initial GlobalState for a pipeline run."""
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
        "xlsx_clicked": False,
        "hyperlinks_unchecked": False,
        "export_ok_pressed": False,
        "filename_built": None,
        "file_saved": False,
        "export_popup_closed": False,
        "app_quit": False,
    }
    return state


@router.post("/run-pipeline", response_model=RunPipelineResponse)
def run_pipeline(request: RunPipelineRequest) -> RunPipelineResponse:
    """Run the full 4-agent pipeline."""
    global _last_state
    start_time = time.time()

    logger.info(
        "API: /run-pipeline called. report_key={}, from_date={}, to_date={}",
        request.report_key, request.from_date, request.to_date,
    )

    try:
        state = _build_initial_state(
            report_key=request.report_key,
            from_date=request.from_date,
            to_date=request.to_date,
        )

        graph = build_orchestrator_graph()
        compiled = graph.compile()
        final_state = compiled.invoke(state)
        _last_state = final_state

        duration = time.time() - start_time
        success = final_state.get("pipeline_status") == "success"

        agents_completed = []
        agent_checks = [
            ("agent1_login", final_state.get("home_screen_ready", False)),
            ("agent2_navigation", final_state.get("file_opened", False)),
            ("agent3_filter", final_state.get("report_generated", False)),
            ("agent4_download", final_state.get("file_saved", False)),
        ]
        for agent_name, agent_success in agent_checks:
            agents_completed.append(AgentResult(
                agent_name=agent_name,
                success=agent_success,
                error=final_state.get("error") if not agent_success else None,
            ))

        return RunPipelineResponse(
            success=success,
            report_key=final_state.get("report_key", settings.report_key),
            filename_saved=final_state.get("filename_built"),
            agents_completed=agents_completed,
            error=final_state.get("error"),
            duration_seconds=round(duration, 2),
        )

    except Exception as exc:
        duration = time.time() - start_time
        logger.error("Pipeline execution error: {}", exc)
        return RunPipelineResponse(
            success=False,
            report_key=request.report_key or settings.report_key,
            error=str(exc),
            duration_seconds=round(duration, 2),
        )


@router.post("/run-agent/{agent_name}", response_model=AgentResult)
def run_single_agent(agent_name: str) -> AgentResult:
    """Run a single agent by name.

    agent_name must be one of: login, navigation, filter, download.
    """
    logger.info("API: /run-agent/{} called.", agent_name)

    agent_map = {
        "login": "agents.agent1_login.graph",
        "navigation": "agents.agent2_navigation.graph",
        "filter": "agents.agent3_filter.graph",
        "download": "agents.agent4_download.graph",
    }

    if agent_name not in agent_map:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent: '{agent_name}'. Valid: {list(agent_map.keys())}",
        )

    try:
        state = _build_initial_state()

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

        compiled = graph.compile()
        final_state = compiled.invoke(state)

        success = final_state.get("error") is None
        return AgentResult(
            agent_name=agent_name,
            success=success,
            error=final_state.get("error"),
        )

    except Exception as exc:
        logger.error("Agent '{}' execution error: {}", agent_name, exc)
        return AgentResult(
            agent_name=agent_name,
            success=False,
            error=str(exc),
        )


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check system health and whether the Excellon app is running."""
    app_running = is_app_running(settings.app_window_title)
    return HealthResponse(
        status="healthy",
        app_running=app_running,
        version="1.0.0",
    )


@router.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Return the status from the last pipeline run."""
    global _last_state
    return StatusResponse(
        pipeline_status=_last_state.get("pipeline_status", "idle"),
        current_agent=_last_state.get("current_agent"),
        error=_last_state.get("error"),
        last_filename=_last_state.get("filename_built"),
    )
