"""LangGraph state machine for Agent 3: Filter."""

from langgraph.graph import StateGraph, END
from orchestrator.state import GlobalState

from agents.agent3_filter.nodes.click_arrow_button import click_arrow_button_node
from agents.agent3_filter.nodes.handle_tax_checkboxes import handle_tax_checkboxes_node
from agents.agent3_filter.nodes.select_date_range_custom import select_date_range_custom_node
from agents.agent3_filter.nodes.enter_from_date import enter_from_date_node
from agents.agent3_filter.nodes.enter_to_date import enter_to_date_node
from agents.agent3_filter.nodes.press_generate_report import press_generate_report_node


def _route(state: GlobalState) -> str:
    """Route based on error state."""
    if state.get("error"):
        return "end"
    return "continue"


def build_filter_graph() -> StateGraph:
    """Build the Agent 3 filter sub-graph.

    Flow:
        1. click_arrow_button   — open filter panel (or skip if already open)
        2. handle_tax_checkboxes — tick Show Taxes / Show Tax Details if configured
        3. select_date_range_custom — select Custom + press TAB to unlock dates
        4. enter_from_date      — type From Date from .env
        5. enter_to_date        — type To Date from .env
        6. press_generate_report — click Generate Report and wait for data
    """
    graph = StateGraph(GlobalState)

    graph.add_node("click_arrow_button", click_arrow_button_node)
    graph.add_node("handle_tax_checkboxes", handle_tax_checkboxes_node)
    graph.add_node("select_date_range_custom", select_date_range_custom_node)
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
