"""
LangGraph coaching agent package.

Public API:
    CoachAgent      — facade class for coaching (proactive / reactive / chat)
    CoachAgentState — TypedDict state flowing through the graph
    create_coach_graph — low-level graph builder
"""

from .state import CoachAgentState
from .graph import create_coach_graph
from .agent import CoachAgent

__all__ = ["CoachAgent", "CoachAgentState", "create_coach_graph"]
