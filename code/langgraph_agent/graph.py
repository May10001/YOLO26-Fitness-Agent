"""
LangGraph state graph for the coaching pipeline.

Linear 3-node graph:
    START → select_system_prompt → build_context → call_dashscope → END

The chat_mode field drives internal branching (proactive vs reactive prompts
and templates) rather than conditional graph edges, keeping the topology simple.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import CoachAgentState
from .nodes import (
    select_system_prompt_node,
    build_context_node,
    call_dashscope_node,
)


def create_coach_graph() -> StateGraph:
    """Build and compile the coaching agent state graph.

    Returns a compiled StateGraph ready for .invoke() or .stream().
    """
    builder = StateGraph(CoachAgentState)

    builder.add_node("select_system_prompt", select_system_prompt_node)
    builder.add_node("build_context", build_context_node)
    builder.add_node("call_dashscope", call_dashscope_node)

    builder.set_entry_point("select_system_prompt")
    builder.add_edge("select_system_prompt", "build_context")
    builder.add_edge("build_context", "call_dashscope")
    builder.add_edge("call_dashscope", END)

    return builder.compile()
