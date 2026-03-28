"""LangGraph state machine for Agent 4: Download.

Sequence:
1. click_export_button   — Click XLSX/CSV/PDF button in toolbar
2. dismiss_export_popup  — Uncheck hyperlinks + press OK (Excel only)
3. handle_save_as        — Rename file, navigate to folder, click Save
4. decline_open_file     — Decline 'open file?' popup
5. close_application     — Alt+F4 + confirm exit
"""

from langgraph.graph import StateGraph, END
from orchestrator.state import GlobalState

from agents.agent4_download.nodes.click_export_button import click_export_button_node
from agents.agent4_download.nodes.dismiss_export_popup import dismiss_export_popup_node
from agents.agent4_download.nodes.handle_save_as import handle_save_as_node
from agents.agent4_download.nodes.decline_open_file import decline_open_file_node
from agents.agent4_download.nodes.close_application import close_application_node


def _route(state: GlobalState) -> str:
    if state.get("error"):
        return "end"
    return "continue"


def build_download_graph() -> StateGraph:
    graph = StateGraph(GlobalState)

    graph.add_node("click_export_button", click_export_button_node)
    graph.add_node("dismiss_export_popup", dismiss_export_popup_node)
    graph.add_node("handle_save_as", handle_save_as_node)
    graph.add_node("decline_open_file", decline_open_file_node)
    graph.add_node("close_application", close_application_node)

    graph.set_entry_point("click_export_button")

    graph.add_conditional_edges(
        "click_export_button", _route,
        {"end": END, "continue": "dismiss_export_popup"},
    )
    graph.add_conditional_edges(
        "dismiss_export_popup", _route,
        {"end": END, "continue": "handle_save_as"},
    )
    graph.add_conditional_edges(
        "handle_save_as", _route,
        {"end": END, "continue": "decline_open_file"},
    )
    graph.add_conditional_edges(
        "decline_open_file", _route,
        {"end": END, "continue": "close_application"},
    )
    graph.add_edge("close_application", END)

    return graph
