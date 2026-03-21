"""LangGraph state machine for Agent 3: Filter."""

from langgraph.graph import StateGraph, END
from orchestrator.state import GlobalState

from agents.agent3_filter.nodes.click_arrow_button import click_arrow_button_node
from agents.agent3_filter.nodes.handle_tax_checkboxes import handle_tax_checkboxes_node
from agents.agent3_filter.nodes.select_date_range_custom import select_date_range_custom_node
from agents.agent3_filter.nodes.press_tab import press_tab_node
from agents.agent3_filter.nodes.enter_from_date import enter_from_date_node
from agents.agent3_filter.nodes.enter_to_date import enter_to_date_node
from agents.agent3_filter.nodes.press_generate_report import press_generate_report_node


def _route(state: GlobalState) -> str:
    """Route based on error state."""
    if state.get("error"):
        return "end"
    return "continue"


def build_filter_graph() -> StateGraph:
    """Build the Agent 3 filter sub-graph."""
    graph = StateGraph(GlobalState)

    graph.add_node("click_arrow_button", click_arrow_button_node)
    graph.add_node("handle_tax_checkboxes", handle_tax_checkboxes_node)
    graph.add_node("select_date_range_custom", select_date_range_custom_node)
    graph.add_node("press_tab", press_tab_node)
    graph.add_node("enter_from_date", enter_from_date_node)
    graph.add_node("enter_to_date", enter_to_date_node)
    graph.add_node("press_generate_report", press_generate_report_node)

    graph.set_entry_point("click_arrow_button")

    graph.add_conditional_edges(
        "click_arrow_button", _route,
        {"end": END, "continue": "handle_tax_checkboxes"},
    )
    graph.add_conditional_edges(
        "handle_tax_checkboxes", _route,
        {"end": END, "continue": "select_date_range_custom"},
    )
    graph.add_conditional_edges(
        "select_date_range_custom", _route,
        {"end": END, "continue": "press_tab"},
    )
    graph.add_conditional_edges(
        "press_tab", _route,
        {"end": END, "continue": "enter_from_date"},
    )
    graph.add_conditional_edges(
        "enter_from_date", _route,
        {"end": END, "continue": "enter_to_date"},
    )
    graph.add_conditional_edges(
        "enter_to_date", _route,
        {"end": END, "continue": "press_generate_report"},
    )
    graph.add_edge("press_generate_report", END)

    return graph
