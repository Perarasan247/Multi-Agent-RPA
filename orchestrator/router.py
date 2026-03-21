"""Routing logic for conditional edges in the orchestrator graph."""

from orchestrator.state import GlobalState


def route_after_agent(state: GlobalState) -> str:
    """Decide whether to continue or fail the pipeline.

    Returns:
        'pipeline_failed' if an error exists in state.
        'continue' otherwise.
    """
    if state.get("error"):
        return "pipeline_failed"
    return "continue"
