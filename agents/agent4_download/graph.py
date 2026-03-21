"""LangGraph state machine for Agent 4: Download."""

from langgraph.graph import StateGraph, END
from orchestrator.state import GlobalState

from agents.agent4_download.nodes.click_xlsx_export import click_xlsx_export_node
from agents.agent4_download.nodes.uncheck_hyperlinks import uncheck_hyperlinks_node
from agents.agent4_download.nodes.press_ok_export import press_ok_export_node
from agents.agent4_download.nodes.handle_file_explorer import handle_file_explorer_node
from agents.agent4_download.nodes.build_filename import build_filename_node
from agents.agent4_download.nodes.press_save import press_save_node
from agents.agent4_download.nodes.handle_export_popup import handle_export_popup_node
from agents.agent4_download.nodes.quit_application import quit_application_node


def _route(state: GlobalState) -> str:
    """Route based on error state."""
    if state.get("error"):
        return "end"
    return "continue"


def build_download_graph() -> StateGraph:
    """Build the Agent 4 download sub-graph."""
    graph = StateGraph(GlobalState)

    graph.add_node("click_xlsx_export", click_xlsx_export_node)
    graph.add_node("uncheck_hyperlinks", uncheck_hyperlinks_node)
    graph.add_node("press_ok_export", press_ok_export_node)
    graph.add_node("handle_file_explorer", handle_file_explorer_node)
    graph.add_node("build_filename", build_filename_node)
    graph.add_node("press_save", press_save_node)
    graph.add_node("handle_export_popup", handle_export_popup_node)
    graph.add_node("quit_application", quit_application_node)

    graph.set_entry_point("click_xlsx_export")

    graph.add_conditional_edges(
        "click_xlsx_export", _route,
        {"end": END, "continue": "uncheck_hyperlinks"},
    )
    graph.add_conditional_edges(
        "uncheck_hyperlinks", _route,
        {"end": END, "continue": "press_ok_export"},
    )
    graph.add_conditional_edges(
        "press_ok_export", _route,
        {"end": END, "continue": "handle_file_explorer"},
    )
    graph.add_conditional_edges(
        "handle_file_explorer", _route,
        {"end": END, "continue": "build_filename"},
    )
    graph.add_conditional_edges(
        "build_filename", _route,
        {"end": END, "continue": "press_save"},
    )
    graph.add_conditional_edges(
        "press_save", _route,
        {"end": END, "continue": "handle_export_popup"},
    )
    graph.add_conditional_edges(
        "handle_export_popup", _route,
        {"end": END, "continue": "quit_application"},
    )
    graph.add_edge("quit_application", END)

    return graph
