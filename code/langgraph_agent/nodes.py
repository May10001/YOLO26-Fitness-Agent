"""
LangGraph agent nodes for the coaching pipeline.

Three nodes:
  1. select_system_prompt  — picks COACH_SYSTEM_PROMPT variant by chat_mode
  2. build_context         — formats scoring data via CoachContextBuilder
  3. call_dashscope        — sends to DashScope QWEN API, returns response
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CoachAgentState

#线性3节点图：select_system_prompt → build_context → call_dashscope

# Node 1: system prompt selection
#根据chat_mode选择不同的系统_prompt模板
def select_system_prompt_node(state: CoachAgentState) -> dict:
    """Pick the right COACH_SYSTEM_PROMPT variant based on chat_mode."""
    from code.coach_system_prompt import (
        COACH_SYSTEM_PROMPT,
        COACH_SYSTEM_PROMPT_PROACTIVE,
    )

    if state.get("chat_mode") == "proactive":
        return {"system_prompt": COACH_SYSTEM_PROMPT_PROACTIVE}
    return {"system_prompt": COACH_SYSTEM_PROMPT}


# Node 2: context building
#根据CoachContextBuilder格式化评分状态
def build_context_node(state: CoachAgentState) -> dict:
    """Build structured Chinese context from scoring state.

    Reconstructs AnalysisResult-like and GuidanceState-like objects from the
    typed state dict, then delegates to CoachContextBuilder (the existing,
    tested formatting logic). No new formatting code — pure bridge.
    """
    from code.realtime_coach import CoachContextBuilder

    score = state.get("score", {})
    angles = state.get("joint_angles", {})
    errors_raw = state.get("errors", [])
    chat_mode = state.get("chat_mode", "reactive")
    exercise_name = state.get("exercise_name", "深蹲")
    user_message = state.get("user_message", "")

    # Reconstruct AnalysisResult-like object
    score_obj = SimpleNamespace(
        total=float(score.get("total", 0)),
        angle_score=float(score.get("angle", 0)),
        temporal_score=float(score.get("temporal", 0)),
        symmetry_score=float(score.get("symmetry", 0)),
    )
    angles_obj = SimpleNamespace(
        knee_left=_float_or_none(angles.get("knee_left")),
        knee_right=_float_or_none(angles.get("knee_right")),
        hip_left=_float_or_none(angles.get("hip_left")),
        hip_right=_float_or_none(angles.get("hip_right")),
        elbow_left=_float_or_none(angles.get("elbow_left")),
        elbow_right=_float_or_none(angles.get("elbow_right")),
        shoulder_left=_float_or_none(angles.get("shoulder_left")),
        shoulder_right=_float_or_none(angles.get("shoulder_right")),
        trunk_angle=_float_or_none(angles.get("trunk_angle")),
        ankle_left=_float_or_none(angles.get("ankle_left")),
        ankle_right=_float_or_none(angles.get("ankle_right")),
    )
    error_objs = [
        SimpleNamespace(
            name=e.get("name", ""),
            severity=int(e.get("severity", 1)),
            message=e.get("message", ""),
            suggestion=e.get("suggestion", ""),
        )
        for e in errors_raw
    ]
    analysis_obj = SimpleNamespace(
        score=score_obj,
        angles=angles_obj,
        phase=state.get("phase", "等待"),
        count=int(state.get("rep_count", 0)),
        hold_time=float(state.get("hold_time", 0)),
        errors=error_objs,
    )

    # Reconstruct GuidanceState-like object
    state_obj = SimpleNamespace(
        recent_scores=[float(x) for x in state.get("recent_scores", [])],
        best_score=float(state.get("best_score", 0)),
        consecutive_good_form=int(state.get("consecutive_good_form", 0)),
        consecutive_bad_form=int(state.get("consecutive_bad_form", 0)),
        error_counts=dict(state.get("error_counts", {})),
    )

    if chat_mode == "proactive":
        context = CoachContextBuilder.build_proactive(
            analysis_obj, state_obj, exercise_name
        )
    else:
        context = CoachContextBuilder.build_reactive(
            analysis_obj, state_obj, exercise_name, user_message
        )

    return {"context_prompt": context}


# Node 3: DashScope LLM call
#将系统_prompt和上下文_prompt发送到DashScope QWEN API，返回教练响应 
def call_dashscope_node(state: CoachAgentState) -> dict:
    """Send system prompt + context to DashScope QWEN API.

    Uses the exact same API pattern as backend/routers/chat.py (OpenAI SDK
    against dashscope.aliyuncs.com). Returns the model's coaching response.
    """
    api_config = state.get("api_config", {})
    if not api_config.get("use_remote") or not api_config.get("api_key"):
        return {"error": "请在项目根目录的 data/api_config.json 中配置 DashScope API 密钥（use_remote, api_key, model_code），以启用AI教练功能。", "response": ""}

    system_prompt = state.get("system_prompt", "")
    context_prompt = state.get("context_prompt", "")

    if not context_prompt:
        return {"error": "No context prompt to send", "response": ""}

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_config["api_key"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        completion = client.chat.completions.create(
            model=api_config.get("model_code", "qwen-plus"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_prompt},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return {"response": completion.choices[0].message.content, "error": ""}
    except Exception as exc:
        return {"response": "", "error": str(exc)}


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
