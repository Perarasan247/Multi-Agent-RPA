"""LangGraph state machine for Agent 2: Navigation."""

from langgraph.graph import StateGraph, END
from orchestrator.state import GlobalState

from agents.agent2_navigation.nodes.read_config import read_config_node
from agents.agent2_navigation.nodes.focus_window import focus_window_node
from agents.agent2_navigation.nodes.type_search import type_search_node
from agents.agent2_navigation.nodes.collect_results import collect_results_node
from agents.agent2_navigation.nodes.exact_match import exact_match_node
from agents.agent2_navigation.nodes.visual_confirm import visual_confirm_node
from agents.agent2_navigation.nodes.click_item import click_item_node
from agents.agent2_navigation.nodes.verify_opened import verify_opened_node


def _route(state: GlobalState) -> str:
    """Route based on error state."""
    if state.get("error"):
        return "end"
    return "continue"


def build_navigation_graph() -> StateGraph:
    """Build the Agent 2 navigation sub-graph."""
    graph = StateGraph(GlobalState)

    graph.add_node("read_config", read_config_node)
    graph.add_node("focus_window", focus_window_node)
    graph.add_node("type_search", type_search_node)
    graph.add_node("collect_results", collect_results_node)
    graph.add_node("find_exact_match", exact_match_node)
    graph.add_node("visual_confirm", visual_confirm_node)
    graph.add_node("click_item", click_item_node)
    graph.add_node("verify_opened", verify_opened_node)

    graph.set_entry_point("read_config")

    graph.add_conditional_edges(
        "read_config", _route,
        {"end": END, "continue": "focus_window"},
    )
    graph.add_conditional_edges(
        "focus_window", _route,
        {"end": END, "continue": "type_search"},
    )
    graph.add_conditional_edges(
        "type_search", _route,
        {"end": END, "continue": "collect_results"},
    )
    graph.add_conditional_edges(
        "collect_results", _route,
        {"end": END, "continue": "find_exact_match"},
    )
    graph.add_conditional_edges(
        "find_exact_match", _route,
        {"end": END, "continue": "visual_confirm"},
    )
    graph.add_conditional_edges(
        "visual_confirm", _route,
        {"end": END, "continue": "click_item"},
    )
    graph.add_conditional_edges(
        "click_item", _route,
        {"end": END, "continue": "verify_opened"},
    )
    graph.add_edge("verify_opened", END)

    return graph
