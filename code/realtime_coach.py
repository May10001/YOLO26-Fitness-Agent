"""
Real-time LLM coaching engine for the YOLO26 fitness system.

Consumes per-frame AnalysisResult and GuidanceState to:
  1. Build structured Chinese context strings for the LLM
  2. Evaluate triggers for proactive coaching interventions
  3. Manage rate limiting and cooldowns

Usage:
    coach = RealTimeCoach()
    context = coach.build_context(analysis, state, exercise_name)
    trigger_context = coach.evaluate_frame(analysis, state, exercise_name)
    if trigger_context:
        # send trigger_context to LLM API in background thread
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .coach_system_prompt import COACH_CONTEXT_TEMPLATE, COACH_REACTIVE_TEMPLATE
from .pose_analyzer import AnalysisResult


# ============================================================================
# Trigger types
# ============================================================================

class TriggerType(Enum):
    SEVERE_ERROR = "severe_error"       # 严重错误 (severity >= 2, 5+ frames)
    SCORE_DROP = "score_drop"           # 评分骤降 (比最佳低15+)
    PERSONAL_BEST = "personal_best"     # 个人最佳 (超最佳5+)
    MILESTONE = "milestone"             # 次数里程碑
    GOOD_STREAK = "good_streak"         # 连续标准10+次
    USER_INITIATED = "user_initiated"   # 用户主动提问


@dataclass
class TriggerEvent:
    type: TriggerType
    priority: int  # 1-4, higher = more important
    context: str


# ============================================================================
# CoachContextBuilder
# ============================================================================

class CoachContextBuilder:
    """Serializes AnalysisResult + guidance state into structured Chinese text."""

    EXERCISE_ENGLISH = {
        "深蹲": "squat", "俯卧撑": "push-up", "平板支撑": "plank",
        "卷腹": "crunch", "开合跳": "jumping jack", "引体向上": "pull-up",
        "臀桥": "glute bridge", "高抬腿": "high knees", "肩推": "shoulder press",
        "侧平举": "lateral raise",
    }

    SEVERITY_ICONS = {1: "💡", 2: "⚡", 3: "⚠"}

    @classmethod
    def build_proactive(cls, analysis: AnalysisResult, state,
                        exercise_name: str) -> str:
        """Build a full structured context for proactive coaching."""
        s = analysis.score
        a = analysis.angles
        exercise_en = cls.EXERCISE_ENGLISH.get(exercise_name, exercise_name)

        hold_line = ""
        if exercise_name == "平板支撑":
            hold_line = f" | 保持时间：{analysis.hold_time:.1f}s"

        errors_block = cls._format_errors(analysis)
        error_ranking = cls._format_error_ranking(state)

        recent = state.recent_scores[-10:] if hasattr(state, 'recent_scores') else []
        avg_score = round(sum(recent) / max(1, len(recent)), 1) if recent else 0

        return COACH_CONTEXT_TEMPLATE.format(
            exercise_cn=exercise_name,
            exercise_en=exercise_en,
            reps=analysis.count,
            phase_cn=analysis.phase,
            hold_line=hold_line,
            total=f"{s.total:.0f}",
            angle=f"{s.angle_score:.0f}",
            temporal=f"{s.temporal_score:.0f}",
            symmetry=f"{s.symmetry_score:.0f}",
            best_score=f"{state.best_score:.0f}",
            avg_score=f"{avg_score:.0f}",
            errors_block=errors_block,
            knee_l=cls._fmt_angle(a.knee_left),
            knee_r=cls._fmt_angle(a.knee_right),
            hip_l=cls._fmt_angle(a.hip_left),
            hip_r=cls._fmt_angle(a.hip_right),
            elbow_l=cls._fmt_angle(a.elbow_left),
            elbow_r=cls._fmt_angle(a.elbow_right),
            trunk=cls._fmt_angle(a.trunk_angle),
            consecutive_good=state.consecutive_good_form,
            consecutive_bad=state.consecutive_bad_form,
            error_ranking=error_ranking,
        )

    @classmethod
    def build_reactive(cls, analysis: Optional[AnalysisResult], state,
                       exercise_name: str, user_message: str) -> str:
        """Build a context string for reactive (user-initiated) chat."""
        if analysis is None:
            return user_message

        s = analysis.score
        errors = analysis.errors
        if errors:
            error_names = "、".join(e.name for e in errors[:3])
            errors_summary = f"当前错误：{error_names}"
        else:
            errors_summary = "当前无检测错误"

        return COACH_REACTIVE_TEMPLATE.format(
            exercise_cn=exercise_name,
            reps=analysis.count,
            total=f"{s.total:.0f}",
            best_score=f"{state.best_score:.0f}",
            errors_summary=errors_summary,
            user_message=user_message,
        )

    @classmethod
    def _format_errors(cls, analysis: AnalysisResult) -> str:
        if not analysis.errors:
            return "当前无检测到的动作错误"
        lines = []
        for e in analysis.errors[:5]:
            icon = cls.SEVERITY_ICONS.get(e.severity, "•")
            lines.append(f"{icon} {e.name}(严重度{e.severity})：{e.suggestion}")
        return "\n".join(lines)

    @classmethod
    def _format_error_ranking(cls, state) -> str:
        ec = getattr(state, 'error_counts', {})
        if not ec:
            return "暂无"
        sorted_errors = sorted(ec.items(), key=lambda x: x[1], reverse=True)
        return "、".join(f"{name}({count}次)" for name, count in sorted_errors[:5])

    @staticmethod
    def _fmt_angle(value) -> str:
        if value is None:
            return "--"
        return f"{value:.0f}"


# ============================================================================
# CoachTriggerEvaluator
# ============================================================================

class CoachTriggerEvaluator:
    """Evaluates per-frame data against trigger rules for proactive coaching."""

    MILESTONES = {5, 10, 15, 20, 30, 50, 100}
    SCORE_DROP_THRESHOLD = 15
    PERSONAL_BEST_DELTA = 5
    GOOD_STREAK_THRESHOLD = 10
    ERROR_PERSISTENCE_FRAMES = 5
    SEVERE_ERROR_SEVERITY = 2

    def __init__(self):
        self._last_count: int = 0
        self._last_best_score: float = -1.0
        self._triggered_milestones: set = set()
        self._triggered_error_types: set = set()

    def reset(self):
        self._last_count = 0
        self._last_best_score = -1.0
        self._triggered_milestones.clear()
        self._triggered_error_types.clear()

    def evaluate(self, analysis: AnalysisResult, state,
                 exercise_name: str) -> Optional[TriggerEvent]:
        """Evaluate all trigger rules, return highest-priority event."""

        # Priority 4: severe error sustained for 5+ frames
        event = self._check_severe_error(analysis, state, exercise_name)
        if event:
            return event

        # Priority 4: score drop
        event = self._check_score_drop(analysis, state, exercise_name)
        if event:
            return event

        # Priority 3: personal best
        event = self._check_personal_best(analysis, state, exercise_name)
        if event:
            return event

        # Priority 2: rep milestone
        event = self._check_milestone(analysis, state, exercise_name)
        if event:
            return event

        # Priority 1: good form streak
        event = self._check_good_streak(analysis, state, exercise_name)
        if event:
            return event

        # Update tracking
        self._last_count = analysis.count
        self._last_best_score = state.best_score
        return None

    def _check_severe_error(self, analysis, state, exercise_name):
        if not analysis.errors:
            return None
        for e in analysis.errors:
            if e.severity >= self.SEVERE_ERROR_SEVERITY:
                frames = getattr(state, 'consecutive_error_frames', {}).get(e.name, 0)
                if frames >= self.ERROR_PERSISTENCE_FRAMES:
                    if e.name not in self._triggered_error_types:
                        self._triggered_error_types.add(e.name)
                        context = CoachContextBuilder.build_proactive(
                            analysis, state, exercise_name
                        )
                        return TriggerEvent(TriggerType.SEVERE_ERROR, 4, context)
        return None

    def _check_score_drop(self, analysis, state, exercise_name):
        if analysis.count < 3:
            return None
        if state.best_score > 0 and analysis.score.total < state.best_score - self.SCORE_DROP_THRESHOLD:
            context = CoachContextBuilder.build_proactive(
                analysis, state, exercise_name
            )
            return TriggerEvent(TriggerType.SCORE_DROP, 4, context)
        return None

    def _check_personal_best(self, analysis, state, exercise_name):
        if analysis.count < 5:
            return None
        if self._last_best_score < 0:
            return None
        if analysis.score.total > self._last_best_score + self.PERSONAL_BEST_DELTA:
            if state.consecutive_good_form >= 3:
                context = CoachContextBuilder.build_proactive(
                    analysis, state, exercise_name
                )
                return TriggerEvent(TriggerType.PERSONAL_BEST, 3, context)
        return None

    def _check_milestone(self, analysis, state, exercise_name):
        count = analysis.count
        if count in self.MILESTONES and count > self._last_count:
            if count not in self._triggered_milestones:
                self._triggered_milestones.add(count)
                context = CoachContextBuilder.build_proactive(
                    analysis, state, exercise_name
                )
                return TriggerEvent(TriggerType.MILESTONE, 2, context)
        return None

    def _check_good_streak(self, analysis, state, exercise_name):
        if state.consecutive_good_form >= self.GOOD_STREAK_THRESHOLD:
            if analysis.score.total > 70:
                if state.consecutive_good_form == self.GOOD_STREAK_THRESHOLD:
                    context = CoachContextBuilder.build_proactive(
                        analysis, state, exercise_name
                    )
                    return TriggerEvent(TriggerType.GOOD_STREAK, 1, context)
        return None


# ============================================================================
# RealTimeCoach
# ============================================================================

class RealTimeCoach:
    """Main coach coordinator: triggers + context + rate limiting."""

    COOLDOWNS = {
        TriggerType.SEVERE_ERROR: 8.0,
        TriggerType.SCORE_DROP: 10.0,
        TriggerType.PERSONAL_BEST: 15.0,
        TriggerType.MILESTONE: 20.0,
        TriggerType.GOOD_STREAK: 30.0,
    }

    GLOBAL_COOLDOWN = 6.0        # min seconds between any two proactive calls
    MAX_PROACTIVE_PER_SESSION = 20

    def __init__(self):
        self.builder = CoachContextBuilder()
        self.evaluator = CoachTriggerEvaluator()
        self._last_trigger_times: dict[TriggerType, float] = {}
        self._last_any_trigger_time: float = 0.0
        self._session_trigger_count: int = 0
        self._user_initiated = False

    def evaluate_frame(self, analysis: AnalysisResult, state,
                       exercise_name: str) -> Optional[str]:
        """Called every frame. Returns context string if a trigger should fire."""
        if self._session_trigger_count >= self.MAX_PROACTIVE_PER_SESSION:
            return None

        now = time.time()
        if now - self._last_any_trigger_time < self.GLOBAL_COOLDOWN:
            return None

        event = self.evaluator.evaluate(analysis, state, exercise_name)
        if event is None:
            return None

        cooldown = self.COOLDOWNS.get(event.type, 15.0)
        last = self._last_trigger_times.get(event.type, 0)
        if now - last < cooldown:
            return None

        self._last_trigger_times[event.type] = now
        self._last_any_trigger_time = now
        self._session_trigger_count += 1
        self._user_initiated = False
        return event.context

    def build_chat_context(self, analysis: Optional[AnalysisResult], state,
                           exercise_name: str, user_message: str) -> str:
        """Build context for a user-initiated chat message."""
        self._user_initiated = True
        if analysis is not None:
            return self.builder.build_reactive(analysis, state, exercise_name, user_message)
        return user_message

    @property
    def is_user_initiated(self) -> bool:
        return self._user_initiated

    def reset(self):
        self.evaluator.reset()
        self._last_trigger_times.clear()
        self._last_any_trigger_time = 0.0
        self._session_trigger_count = 0
