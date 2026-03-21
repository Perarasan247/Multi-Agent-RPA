"""Master orchestrator LangGraph pipeline.

Runs 4 agents sequentially: login → navigation → filter → download.
Each agent is a compiled sub-graph invoked as a node.
Conditional edges route to pipeline_failed on any error.
"""

from loguru import logger
from langgraph.graph import StateGraph, END

from orchestrator.state import GlobalState
from orchestrator.router import route_after_agent

from agents.agent1_login.graph import build_login_graph
from agents.agent2_navigation.graph import build_navigation_graph
from agents.agent3_filter.graph import build_filter_graph
from agents.agent4_download.graph import build_download_graph


def _run_agent1(state: GlobalState) -> GlobalState:
    """Execute Agent 1: Login."""
    logger.info("═══ Starting Agent 1: Login ═══")
    state["current_agent"] = "agent1_login"
    graph = build_login_graph()
    compiled = graph.compile()
    result = compiled.invoke(state)
    state.update(result)
    logger.info("═══ Agent 1 finished. Error: {} ═══", state.get("error"))
    return state


def _run_agent2(state: GlobalState) -> GlobalState:
    """Execute Agent 2: Navigation."""
    logger.info("═══ Starting Agent 2: Navigation ═══")
    state["current_agent"] = "agent2_navigation"
    graph = build_navigation_graph()
    compiled = graph.compile()
    result = compiled.invoke(state)
    state.update(result)
    logger.info("═══ Agent 2 finished. Error: {} ═══", state.get("error"))
    return state


def _run_agent3(state: GlobalState) -> GlobalState:
    """Execute Agent 3: Filter ."""
    logger.info("═══ Starting Agent 3: Filter ═══")
    state["current_agent"] = "agent3_filter"
    graph = build_filter_graph()
    compiled = graph.compile()
    result = compiled.invoke(state)
    state.update(result)
    logger.info("═══ Agent 3 finished. Error: {} ═══", state.get("error"))
    return state


def _run_agent4(state: GlobalState) -> GlobalState:
    """Execute Agent 4: Download."""
    logger.info("═══ Starting Agent 4: Download ═══")
    state["current_agent"] = "agent4_download"
    graph = build_download_graph()
    compiled = graph.compile()
    result = compiled.invoke(state)
    state.update(result)
    logger.info("═══ Agent 4 finished. Error: {} ═══", state.get("error"))
    return state


def _pipeline_failed(state: GlobalState) -> GlobalState:
    """Handle pipeline failure."""
    logger.error(
        "Pipeline FAILED at agent '{}': {}",
        state.get("current_agent", "unknown"),
        state.get("error", "Unknown error"),
    )
    state["pipeline_status"] = "failed"
    return state


def _pipeline_success(state: GlobalState) -> GlobalState:
    """Mark pipeline as successful."""
    logger.info("Pipeline completed successfully.")
    state["pipeline_status"] = "success"
    return state


def build_orchestrator_graph() -> StateGraph:
    """Build the master orchestrator state graph."""
    graph = StateGraph(GlobalState)

    # Add nodes
    graph.add_node("run_agent1", _run_agent1)
    graph.add_node("run_agent2", _run_agent2)
    graph.add_node("run_agent3", _run_agent3)
    graph.add_node("run_agent4", _run_agent4)
    graph.add_node("pipeline_failed", _pipeline_failed)
    graph.add_node("pipeline_success", _pipeline_success)

    # Entry point
    graph.set_entry_point("run_agent1")

    # Conditional edges after each agent
    graph.add_conditional_edges(
        "run_agent1",
        route_after_agent,
        {"pipeline_failed": "pipeline_failed", "continue": "run_agent2"},
    )
    graph.add_conditional_edges(
        "run_agent2",
        route_after_agent,
        {"pipeline_failed": "pipeline_failed", "continue": "run_agent3"},
    )
    graph.add_conditional_edges(
        "run_agent3",
        route_after_agent,
        {"pipeline_failed": "pipeline_failed", "continue": "run_agent4"},
    )
    graph.add_conditional_edges(
        "run_agent4",
        route_after_agent,
        {"pipeline_failed": "pipeline_failed", "continue": "pipeline_success"},
    )

    # Terminal nodes
    graph.add_edge("pipeline_failed", END)
    graph.add_edge("pipeline_success", END)

    return graph
