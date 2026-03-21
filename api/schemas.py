"""Pydantic schemas for the RPA API."""

from pydantic import BaseModel


class RunPipelineRequest(BaseModel):
    """Request body for running the full pipeline."""
    report_key: str | None = None
    from_date: str | None = None
    to_date: str | None = None


class AgentResult(BaseModel):
    """Result from a single agent execution."""
    agent_name: str
    success: bool
    error: str | None = None


class RunPipelineResponse(BaseModel):
    """Response from a full pipeline run."""
    success: bool
    report_key: str
    filename_saved: str | None = None
    agents_completed: list[AgentResult] = []
    error: str | None = None
    duration_seconds: float = 0.0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    app_running: bool
    version: str = "1.0.0"


class StatusResponse(BaseModel):
    """Pipeline status response."""
    pipeline_status: str
    current_agent: str | None = None
    error: str | None = None
    last_filename: str | None = None
