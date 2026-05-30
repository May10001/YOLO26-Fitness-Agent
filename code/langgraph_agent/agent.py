"""
LangGraph-powered coaching agent facade.

Provides three interfaces:
  1. coach_proactive() — auto-push coaching on trigger events
  2. coach_reactive()  — user-initiated chat with full pose context
  3. chat()            — simplified string-in/string-out, compatible with
                         existing FitnessAgent.chat() patterns

Usage:
    agent = CoachAgent()
    result = agent.coach_reactive("我的姿势怎么样？", analysis, state, "深蹲")
    print(result["response"])
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .state import CoachAgentState, state_from_analysis, state_from_dict
from .graph import create_coach_graph

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_api_config() -> dict:
    for name in ["api_config.json", "data/api_config.json"]:
        path = PROJECT_ROOT / name
        if path.exists():
            return json.loads(path.read_text())
    return {"use_remote": False, "api_key": "", "model_code": ""}


class CoachAgent:
    """LangGraph coaching agent wrapping the 3-node pipeline.

    Accepts api_config at construction time; falls back to reading
    data/api_config.json from the project root (same as backend/routers/chat.py).
    """

    def __init__(self, api_config: dict | None = None):
        self._graph = create_coach_graph()
        self._api_config = api_config or _load_api_config()

    # ------------------------------------------------------------------
    # Proactive coaching (auto-push on trigger)
    # ------------------------------------------------------------------

    def coach_proactive(self, analysis_result, guidance_state,
                        exercise_name: str) -> dict:
        """Build state from live AnalysisResult + GuidanceState, invoke graph.

        Args:
            analysis_result: code.pose_analyzer.AnalysisResult
            guidance_state: code.guidance.context_engine.GuidanceState
            exercise_name: Chinese exercise name

        Returns:
            {"response": str, "error": str, ...} — full state after graph run
        """
        state = state_from_analysis(
            analysis_result, guidance_state, exercise_name,
            chat_mode="proactive", api_config=self._api_config,
        )
        return self._graph.invoke(state)

    # ------------------------------------------------------------------
    # Reactive coaching (user-initiated chat with pose context)
    # ------------------------------------------------------------------

    def coach_reactive(self, user_message: str, analysis_result=None,
                       guidance_state=None,
                       exercise_name: str = "深蹲") -> dict:
        """User asks a question; include current training state for context.

        Args:
            user_message: User's chat message in Chinese
            analysis_result: Optional current-frame AnalysisResult
            guidance_state: Optional GuidanceState with session history
            exercise_name: Chinese exercise name

        Returns:
            {"response": str, "error": str, ...}
        """
        if analysis_result is not None and guidance_state is not None:
            state = state_from_analysis(
                analysis_result, guidance_state, exercise_name,
                chat_mode="reactive", user_message=user_message,
                api_config=self._api_config,
            )
        else:
            # No live pose data — send user message directly
            state: CoachAgentState = {
                "exercise_name": exercise_name,
                "score": {},
                "joint_angles": {},
                "phase": "等待",
                "rep_count": 0,
                "hold_time": 0.0,
                "errors": [],
                "best_score": 0.0,
                "consecutive_good_form": 0,
                "consecutive_bad_form": 0,
                "error_counts": {},
                "recent_scores": [],
                "chat_mode": "reactive",
                "user_message": user_message,
                "api_config": self._api_config,
                "system_prompt": "",
                "context_prompt": "",
                "response": "",
                "error": "",
            }
        return self._graph.invoke(state)

    # ------------------------------------------------------------------
    # Simplified chat interface (compatible with existing patterns)
    # ------------------------------------------------------------------

    def chat(self, user_message: str,
             pose_context_str: str | None = None) -> str:
        """String-in/string-out chat, compatible with FitnessAgent.chat().

        If pose_context_str is provided and parseable as JSON, it is used
        as structured training context. Otherwise the message is sent as-is.
        """
        if pose_context_str:
            try:
                data = json.loads(pose_context_str)
                chat_mode = data.get("chat_mode", "reactive")
                state = state_from_dict(
                    data, chat_mode=chat_mode,
                    user_message=user_message,
                    api_config=self._api_config,
                )
                result = self._graph.invoke(state)
                return result.get("response", "") or result.get("error", "")
            except json.JSONDecodeError:
                pass

        # Fallback: plain chat without structured pose context
        state: CoachAgentState = {
            "exercise_name": "深蹲",
            "score": {},
            "joint_angles": {},
            "phase": "等待",
            "rep_count": 0,
            "hold_time": 0.0,
            "errors": [],
            "best_score": 0.0,
            "consecutive_good_form": 0,
            "consecutive_bad_form": 0,
            "error_counts": {},
            "recent_scores": [],
            "chat_mode": "reactive",
            "user_message": user_message,
            "api_config": self._api_config,
            "system_prompt": "",
            "context_prompt": "",
            "response": "",
            "error": "",
        }
        result = self._graph.invoke(state)
        return result.get("response", "") or result.get("error", "")


# ------------------------------------------------------------------
# Self-test (python -m code.langgraph_agent.agent)
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("=== LangGraph CoachAgent self-test ===")

    agent = CoachAgent()
    api_ok = bool(agent._api_config.get("use_remote")
                  and agent._api_config.get("api_key"))
    print(f"API config loaded: remote={agent._api_config.get('use_remote')}, "
          f"model={agent._api_config.get('model_code', 'N/A')}")

    # Test 1: state construction (no API needed)
    print("\n[Test 1] State construction...")
    state = state_from_dict({
        "exercise_name": "深蹲",
        "score": {"total": 85, "angle": 34, "temporal": 26, "symmetry": 25},
        "joint_angles": {"knee_left": 95, "knee_right": 92},
        "phase": "低位",
        "rep_count": 10,
        "errors": [],
        "best_score": 85,
        "recent_scores": [82, 84, 85],
    }, chat_mode="reactive", user_message="我的深蹲怎么样？")
    print(f"  State built: exercise={state['exercise_name']}, "
          f"score={state['score']}, rep_count={state['rep_count']}")
    print("  OK")

    # Test 2: graph compilation (no API needed)
    print("\n[Test 2] Graph compilation...")
    from .graph import create_coach_graph
    graph = create_coach_graph()
    print(f"  Graph compiled: nodes={list(graph.nodes.keys())}")
    print("  OK")

    # Test 3: dry-run through nodes (no actual API call — will fail at
    # call_dashscope_node due to no api_key unless configured)
    if api_ok:
        print("\n[Test 3] Full graph invocation (API configured)...")
        result = agent.chat("我的深蹲怎么样？", json.dumps({
            "exercise_name": "深蹲",
            "score": {"total": 85, "angle": 34, "temporal": 26, "symmetry": 25},
            "joint_angles": {"knee_left": 95, "knee_right": 92, "hip_left": 80,
                             "hip_right": 78, "elbow_left": None, "elbow_right": None,
                             "shoulder_left": None, "shoulder_right": None,
                             "trunk_angle": 10, "ankle_left": None, "ankle_right": None},
            "phase": "低位",
            "rep_count": 10,
            "errors": [],
            "best_score": 85,
            "recent_scores": [82, 84, 85],
        }))
        print(f"  Response: {result[:200]}...")
        print("  OK")
    else:
        print("\n[Test 3] Skipped (no remote API configured).")
        print("  Set up data/api_config.json with DashScope credentials to test.")

    print("\n=== All local tests passed ===")
