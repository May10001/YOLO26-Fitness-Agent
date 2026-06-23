"""
LangGraph agent state definition for the coaching pipeline.

Defines CoachAgentState TypedDict — the fixed-format state that bridges
AnalysisResult + GuidanceState → CoachContextBuilder → DashScope QWEN API.
"""

from __future__ import annotations

from typing import TypedDict


class CoachAgentState(TypedDict, total=False):
    """State flowing through the coaching LangGraph pipeline.

    Input fields (set by caller before graph invocation):
        exercise_name:      Chinese exercise name (e.g. "深蹲")
        score:              {total, angle, temporal, symmetry} from ScoreResult
        joint_angles:       {knee_left, knee_right, hip_left, ...} from JointAngles
        phase:              Current movement phase
        rep_count:          Repetition count
        hold_time:          Hold time in seconds (for plank-style exercises)
        errors:             [{name, severity, message, suggestion}, ...]
        best_score:         Session best score
        consecutive_good_form:  Counter of consecutive good-form frames
        consecutive_bad_form:   Counter of consecutive bad-form frames
        error_counts:       {error_name: count} histogram
        recent_scores:      Last N total scores (floats)
        chat_mode:          "proactive" or "reactive"
        user_message:       User's chat message (reactive mode only)
        api_config:         {use_remote, api_key, model_code} from api_config.json
        scorer_data:        Diagnostic data from MovementScorer.get_diagnostic_data()
        cue_history:        Historical cue records [{cue, tier, focus, target_error, ...}]
        cue_effectiveness:  {error_name: {last_cue, effective, tried_cues}}

    Intermediate fields (populated by graph nodes):
        system_prompt:      Selected COACH_SYSTEM_PROMPT variant
        context_prompt:     Formatted COACH_CONTEXT_TEMPLATE string

    Output fields (populated by graph nodes):
        response:           LLM response text (user-facing guidance, backward compat)
        diagnosis_json:     Parsed diagnosis JSON from LLM output
        guidance_text:      User-facing guidance text (explicit naming)
        recommended_cues:   [{cue, tier, focus}] extracted from diagnosis
        error:              Error message if any node fails
    """

    # --- Input: scoring data ---
    exercise_name: str
    score: dict
    joint_angles: dict
    phase: str
    rep_count: int
    hold_time: float
    errors: list[dict]
    best_score: float
    consecutive_good_form: int
    consecutive_bad_form: int
    error_counts: dict[str, int]
    recent_scores: list[float]

    # --- Input: routing ---
    chat_mode: str                  # "proactive" | "reactive"
    user_message: str
    api_config: dict

    # --- Input: diagnostic data (Phase 1/2) ---
    scorer_data: dict               # From MovementScorer.get_diagnostic_data()
    cue_history: list[dict]         # Historical cue records
    cue_effectiveness: dict         # {error_name: {last_cue, effective, tried_cues}}

    # --- Intermediate ---
    system_prompt: str
    context_prompt: str

    # --- Output ---
    response: str                   # Backward-compat: user-facing guidance text
    diagnosis_json: dict            # LLM diagnostic output (Phase 3)
    guidance_text: str              # Explicit guidance text (Phase 3)
    recommended_cues: list[dict]    # [{cue, tier, focus}] (Phase 3)
    error: str


def state_from_analysis(analysis_result, guidance_state, exercise_name: str,
                        chat_mode: str = "proactive", user_message: str = "",
                        api_config: dict | None = None,
                        scorer_data: dict | None = None,
                        cue_effectiveness: dict | None = None) -> CoachAgentState:
    """Build CoachAgentState from existing AnalysisResult + GuidanceState objects.

    This is the primary bridge between the existing scoring pipeline and the
    LangGraph agent. It serializes dataclass instances into the typed dict
    format expected by the graph nodes.

    Args:
        analysis_result: code.pose_analyzer.AnalysisResult instance
        guidance_state: code.guidance.context_engine.GuidanceState instance
        exercise_name: Chinese exercise name
        chat_mode: "proactive" for auto-push, "reactive" for user-initiated
        user_message: User's chat text (only for reactive mode)
        api_config: Remote API config dict (loaded from api_config.json)
        scorer_data: Optional diagnostic data from MovementScorer.get_diagnostic_data()
        cue_effectiveness: Optional cue tracking feedback dict

    Returns:
        CoachAgentState ready for graph invocation
    """
    a = analysis_result
    s = a.score
    ang = a.angles
    gs = guidance_state

    state: CoachAgentState = {
        "exercise_name": exercise_name,
        "score": {
            "total": float(s.total),
            "angle": float(s.angle_score),
            "temporal": float(s.temporal_score),
            "symmetry": float(s.symmetry_score),
        },
        "joint_angles": {
            "knee_left": _maybe_float(ang.knee_left),
            "knee_right": _maybe_float(ang.knee_right),
            "hip_left": _maybe_float(ang.hip_left),
            "hip_right": _maybe_float(ang.hip_right),
            "elbow_left": _maybe_float(ang.elbow_left),
            "elbow_right": _maybe_float(ang.elbow_right),
            "shoulder_left": _maybe_float(ang.shoulder_left),
            "shoulder_right": _maybe_float(ang.shoulder_right),
            "trunk_angle": _maybe_float(ang.trunk_angle),
            "ankle_left": _maybe_float(ang.ankle_left),
            "ankle_right": _maybe_float(ang.ankle_right),
        },
        "phase": a.phase,
        "rep_count": a.count,
        "hold_time": a.hold_time,
        "errors": [
            {
                "name": e.name,
                "severity": e.severity,
                "message": e.message,
                "suggestion": e.suggestion,
            }
            for e in (a.errors or [])
        ],
        "best_score": float(getattr(gs, "best_score", 0)),
        "consecutive_good_form": int(getattr(gs, "consecutive_good_form", 0)),
        "consecutive_bad_form": int(getattr(gs, "consecutive_bad_form", 0)),
        "error_counts": dict(getattr(gs, "error_counts", {})),
        "recent_scores": [
            float(x) for x in getattr(gs, "recent_scores", [])[-30:]
        ],
        "chat_mode": chat_mode,
        "user_message": user_message,
        "api_config": api_config or {},
        "scorer_data": scorer_data or {},
        "cue_history": list(getattr(gs, "cue_history", [])),
        "cue_effectiveness": cue_effectiveness or {},
        "system_prompt": "",
        "context_prompt": "",
        "response": "",
        "diagnosis_json": {},
        "guidance_text": "",
        "recommended_cues": [],
        "error": "",
    }
    return state


def state_from_dict(data: dict, chat_mode: str = "reactive",
                    user_message: str = "",
                    api_config: dict | None = None) -> CoachAgentState:
    """Build CoachAgentState from a JSON-deserialized dict (e.g. from HTTP request).
    这是LangGraph管道的主要桥梁，它将JSON反序列化为CoachAgentState实例。这是LangGraph节点期望的格式。
    Args:
        data: Dict with scoring fields matching CoachAgentState keys
        chat_mode: "proactive" or "reactive"
        user_message: User's chat message
        api_config: Remote API config

    Returns:
        CoachAgentState ready for graph invocation
    """
    state: CoachAgentState = {
        "exercise_name": data.get("exercise_name", "深蹲"),
        "score": data.get("score", {}),
        "joint_angles": data.get("joint_angles", {}),
        "phase": data.get("phase", "等待"),
        "rep_count": data.get("rep_count", 0),
        "hold_time": data.get("hold_time", 0.0),
        "errors": data.get("errors", []),
        "best_score": float(data.get("best_score", 0)),
        "consecutive_good_form": int(data.get("consecutive_good_form", 0)),
        "consecutive_bad_form": int(data.get("consecutive_bad_form", 0)),
        "error_counts": data.get("error_counts", {}),
        "recent_scores": [float(x) for x in data.get("recent_scores", [])],
        "chat_mode": chat_mode,
        "user_message": user_message,
        "api_config": api_config or {},
        "system_prompt": "",
        "context_prompt": "",
        "response": "",
        "error": "",
    }
    return state


def _maybe_float(value) -> float | None:
    """Convert a value to float, returning None if it is None or NaN."""
    if value is None:
        return None
    try:
        f = float(value)
        return f if f == f else None  # guard against NaN
    except (ValueError, TypeError):
        return None
