"""LangGraph state machine for Agent 1: Login."""

from langgraph.graph import StateGraph, END
from orchestrator.state import GlobalState

from agents.agent1_login.nodes.launch_app import launch_app_node
from agents.agent1_login.nodes.wait_for_login_screen import wait_for_login_screen_node
from agents.agent1_login.nodes.type_credentials import type_credentials_node
from agents.agent1_login.nodes.press_connect import press_connect_node
from agents.agent1_login.nodes.handle_popups_pre import handle_popups_pre_node
from agents.agent1_login.nodes.wait_for_fullscreen import wait_for_fullscreen_node
from agents.agent1_login.nodes.handle_popup_post import handle_popup_post_node
from agents.agent1_login.nodes.verify_home_screen import verify_home_screen_node


def _route(state: GlobalState) -> str:
    """Route based on error state."""
    if state.get("error"):
        return "end"
    return "continue"


def _route_after_login_screen(state: GlobalState) -> str:
    """Skip the full login flow if already logged in."""
    if state.get("error"):
        return "end"
    if state.get("already_logged_in"):
        return "already_logged_in"
    return "continue"


def build_login_graph() -> StateGraph:
    """Build the Agent 1 login sub-graph."""
    graph = StateGraph(GlobalState)

    graph.add_node("launch_app", launch_app_node)
    graph.add_node("wait_for_login_screen", wait_for_login_screen_node)
    graph.add_node("type_credentials", type_credentials_node)
    graph.add_node("press_connect", press_connect_node)
    graph.add_node("handle_popups_pre", handle_popups_pre_node)
    graph.add_node("wait_for_fullscreen", wait_for_fullscreen_node)
    graph.add_node("handle_popup_post", handle_popup_post_node)
    graph.add_node("verify_home_screen", verify_home_screen_node)

    graph.set_entry_point("launch_app")

    graph.add_conditional_edges(
        "launch_app", _route,
        {"end": END, "continue": "wait_for_login_screen"},
    )
    graph.add_conditional_edges(
        "wait_for_login_screen", _route_after_login_screen,
        {"end": END, "continue": "type_credentials", "already_logged_in": "verify_home_screen"},
    )
    graph.add_conditional_edges(
        "type_credentials", _route,
        {"end": END, "continue": "press_connect"},
    )
    graph.add_conditional_edges(
        "press_connect", _route,
        {"end": END, "continue": "handle_popups_pre"},
    )
    graph.add_conditional_edges(
        "handle_popups_pre", _route,
        {"end": END, "continue": "wait_for_fullscreen"},
    )
    graph.add_conditional_edges(
        "wait_for_fullscreen", _route,
        {"end": END, "continue": "handle_popup_post"},
    )
    graph.add_conditional_edges(
        "handle_popup_post", _route,
        {"end": END, "continue": "verify_home_screen"},
    )
    graph.add_edge("verify_home_screen", END)

    return graph
