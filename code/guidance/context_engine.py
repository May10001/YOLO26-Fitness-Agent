"""
Context-aware real-time coaching engine.

Consumes AnalysisResult from PoseAnalyzer and generates structured
guidance messages of four types:
  1. Form correction (from detected errors)
  2. Performance feedback (from scores)
  3. Motivational cues (based on rep count milestones)
  4. Safety warnings (when dangerous form detected)

Maintains state across frames to avoid repetitive guidance.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..pose_analyzer import AnalysisResult


class GuidanceType(Enum):
    FORM_CORRECTION = "form_correction"   # 动作纠正
    PERFORMANCE = "performance"            # 表现反馈
    MOTIVATION = "motivation"              # 鼓励
    SAFETY = "safety"                      # 安全警告


@dataclass
class GuidanceMessage:
    """A single guidance message with metadata."""
    type: GuidanceType
    priority: int       # 1=low, 2=medium, 3=high, 4=critical
    text: str            # Chinese guidance text
    timestamp: float = field(default_factory=time.time)


class GuidanceState:
    """Tracks per-exercise session state for guidance decisions."""

    def __init__(self):
        self.total_reps: int = 0
        self.last_milestone: int = 0
        self.consecutive_good_form: int = 0
        self.consecutive_bad_form: int = 0
        self.best_score: float = 0.0
        self.recent_scores: list[float] = []
        self.error_counts: dict[str, int] = {}
        self.guidance_history: list[GuidanceMessage] = []
        self.session_start: float = time.time()
        self.last_proactive_time: float = 0.0
        self.proactive_count: int = 0
        self.last_milestone_count: int = 0
        self.consecutive_error_frames: dict[str, int] = {}

        # --- Cue 效果追踪 (Phase 4) ---
        self.cue_history: list[dict] = []
        # 每条记录: {cue, tier, focus, target_error, timestamp,
        #            error_resolved, frames_to_resolve}
        self.last_active_cues: dict[str, str] = {}
        # key = 错误名, value = 最后使用的 cue 文本
        self._cue_frame_counters: dict[str, int] = {}
        # key = cue 文本, value = 自给出后经过的帧数
        self._RESOLVE_WINDOW = 30  # 多少帧内错误消失视为 cue 有效

    def update(self, result: AnalysisResult):
        """Update state from one analysis frame."""
        self.total_reps = result.count
        self.recent_scores.append(result.score.total)
        if len(self.recent_scores) > 30:
            self.recent_scores.pop(0)

        if result.score.total > self.best_score:
            self.best_score = result.score.total

        # Track milestone changes
        if result.count > self.last_milestone_count:
            self.last_milestone_count = result.count

        if not result.errors:
            self.consecutive_good_form += 1
            self.consecutive_bad_form = 0
            self.consecutive_error_frames.clear()

            # Phase 4: Check if pending cues have resolved
            self._check_cue_resolution(set())
        else:
            self.consecutive_bad_form += 1
            self.consecutive_good_form = 0
            current_errors = set()
            for err in result.errors:
                self.error_counts[err.name] = self.error_counts.get(err.name, 0) + 1
                self.consecutive_error_frames[err.name] = \
                    self.consecutive_error_frames.get(err.name, 0) + 1
                current_errors.add(err.name)

            # Phase 4: Check if pending cues have resolved
            self._check_cue_resolution(current_errors)

    def _check_cue_resolution(self, current_errors: set):
        """Check unresolved cues — if target error is gone, mark as resolved."""
        for cue_entry in self.cue_history:
            if cue_entry.get("error_resolved", False):
                continue
            target = cue_entry.get("target_error", "")
            cue_text = cue_entry.get("cue", "")
            # Increment frame counter
            self._cue_frame_counters[cue_text] = \
                self._cue_frame_counters.get(cue_text, 0) + 1

            if target and target not in current_errors:
                # Error disappeared — check if within resolve window
                frames = self._cue_frame_counters.get(cue_text, 0)
                if frames <= self._RESOLVE_WINDOW:
                    cue_entry["error_resolved"] = True
                    cue_entry["frames_to_resolve"] = frames
                # else: too slow — probably not cue's effect


class ContextEngine:
    """Real-time coaching engine consuming AnalysisResult.

    Usage:
        engine = ContextEngine("深蹲")
        result = analyzer.analyze_frame(keypoints, confs)
        guidance = engine.process(result)
        if guidance:
            print(guidance.text)
    """

    COOLDOWNS = {
        GuidanceType.FORM_CORRECTION: 3.0,
        GuidanceType.PERFORMANCE: 8.0,
        GuidanceType.MOTIVATION: 12.0,
        GuidanceType.SAFETY: 2.0,
    }

    # 总分高于此阈值时，禁用所有 safety/form_correction/performance 提示
    SUPPRESS_SCORE_THRESHOLD = 80

    MOTIVATION_MILESTONES = {5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100}

    MILESTONE_MESSAGES = {
        5: "已经完成5次了，热身结束，正式开始！",
        10: "10次完成！状态不错，保持节奏",
        15: "15次！已经过半了，加油！",
        20: "20次！出色的坚持，感受肌肉的发力",
        25: "25次！你比想象中更强",
        30: "30次！完成一组了，很棒！",
        40: "40次！耐力惊人，继续保持",
        50: "50次！突破自我，值得鼓励！",
        75: "75次！接近专业水平了",
        100: "100次！完美达成目标！",
    }

    def __init__(self, exercise_name: str):
        self.exercise_name = exercise_name
        self.state = GuidanceState()
        self._last_guidance: dict[GuidanceType, GuidanceMessage] = {}
        self._last_timestamp: dict[GuidanceType, float] = {}

    def process(self, result: AnalysisResult) -> Optional[GuidanceMessage]:
        """Main entry point. Returns the highest-priority guidance to show now."""
        self.state.update(result)

        candidates: list[GuidanceMessage] = []

        safety = self._check_safety(result)
        if safety:
            candidates.append(safety)

        correction = self._check_form_correction(result)
        if correction:
            candidates.append(correction)

        perf = self._check_performance(result)
        if perf:
            candidates.append(perf)

        motivation = self._check_motivation(result)
        if motivation:
            candidates.append(motivation)

        if not candidates:
            return None

        candidates.sort(key=lambda g: g.priority, reverse=True)

        for candidate in candidates:
            if self._on_cooldown(candidate.type):
                continue
            self._last_guidance[candidate.type] = candidate
            self._last_timestamp[candidate.type] = time.time()
            self.state.guidance_history.append(candidate)
            return candidate

        return None

    def _on_cooldown(self, gtype: GuidanceType) -> bool:
        """Check if this guidance type is on cooldown."""
        last_ts = self._last_timestamp.get(gtype, 0)
        cooldown = self.COOLDOWNS.get(gtype, 5.0)
        return (time.time() - last_ts) < cooldown

    def _check_safety(self, result: AnalysisResult) -> Optional[GuidanceMessage]:
        """Safety warnings for dangerous form (priority 4)."""
        if result.score.total > self.SUPPRESS_SCORE_THRESHOLD:
            return None
        for err in result.errors:
            if err.severity >= 2:
                return GuidanceMessage(
                    type=GuidanceType.SAFETY,
                    priority=4,
                    text=f"⚠ 安全警告：{err.suggestion}",
                )
        if result.temporal.angular_velocity > 300:
            return GuidanceMessage(
                type=GuidanceType.SAFETY,
                priority=3,
                text="⚠ 动作速度过快，请放慢节奏，控制动作质量，避免受伤",
            )
        return None

    def _check_form_correction(self, result: AnalysisResult) -> Optional[GuidanceMessage]:
        """Form correction from detected errors (priority 3)."""
        if result.score.total > self.SUPPRESS_SCORE_THRESHOLD:
            return None
        if not result.errors:
            return None
        worst = max(result.errors, key=lambda e: e.severity)
        return GuidanceMessage(
            type=GuidanceType.FORM_CORRECTION,
            priority=3,
            text=f"✏ 纠正：{worst.suggestion}",
        )

    def _check_performance(self, result: AnalysisResult) -> Optional[GuidanceMessage]:
        """Performance feedback based on score (priority 2)."""
        if result.score.total > self.SUPPRESS_SCORE_THRESHOLD:
            return None
        if result.phase == "等待" or result.count == 0:
            return None

        # 如果有总体评分报告, 使用更丰富的反馈
        if result.overall is not None:
            overall = result.overall
            if overall.grade == "优秀":
                return GuidanceMessage(
                    type=GuidanceType.PERFORMANCE,
                    priority=2,
                    text=f"🌟 {overall.grade_emoji} 总体评分 {overall.total_score:.0f} 分 — {overall.grade_message}",
                )
            elif overall.grade == "需改进":
                return GuidanceMessage(
                    type=GuidanceType.PERFORMANCE,
                    priority=2,
                    text=f"📊 {overall.grade_emoji} 总体评分 {overall.total_score:.0f} 分。{overall.suggestion}",
                )

        if result.score.total < 30:
            return GuidanceMessage(
                type=GuidanceType.PERFORMANCE,
                priority=2,
                text=(f"📊 当前评分 {result.score.total:.0f} 分，动作质量需要改善。"
                      f"注意角度控制 ({result.score.angle_score:.0f}/40) 和节奏 ({result.score.temporal_score:.0f}/30)"),
            )
        if result.score.total >= 85 and self.state.total_reps > 3:
            return GuidanceMessage(
                type=GuidanceType.PERFORMANCE,
                priority=2,
                text=f"🌟 优秀！当前评分 {result.score.total:.0f} 分，动作非常标准，继续保持！",
            )
        return None

    def _check_motivation(self, result: AnalysisResult) -> Optional[GuidanceMessage]:
        """Motivational cues at rep milestones (priority 1)."""
        reps = result.count
        if reps in self.MOTIVATION_MILESTONES and reps > self.state.last_milestone:
            self.state.last_milestone = reps
            text = self.MILESTONE_MESSAGES.get(
                reps, f"已完成 {reps} 次，继续加油！"
            )
            return GuidanceMessage(
                type=GuidanceType.MOTIVATION,
                priority=1,
                text=f"💪 {text}",
            )
        return None

    def get_summary_context(self) -> str:
        """Return a text summary of current state for LLM context injection."""
        return (
            f"当前动作: {self.exercise_name}, "
            f"已完成: {self.state.total_reps}次, "
            f"最佳评分: {self.state.best_score:.0f}分"
        )

    # Mapping from internal phase names to standard exercise science terminology
    PHASE_MAP = {
        "高位": "向心收缩",
        "低位": "离心收缩",
        "保持": "等长保持",
        "等待": "等待",
        "姿态调整": "等待",
    }

    # Chinese → English exercise name mapping
    EXERCISE_EN_MAP = {
        "深蹲": "squat",
        "俯卧撑": "push-up",
        "平板支撑": "plank",
        "卷腹": "crunch",
        "开合跳": "jumping jack",
        "引体向上": "pull-up",
        "臀桥": "glute bridge",
        "高抬腿": "high knees",
        "肩推": "shoulder press",
        "侧平举": "lateral raise",
    }

    def build_coach_context_json(self, result: AnalysisResult) -> dict:
        """Build a JSON-serializable coaching context dict for LLM prompt injection.

        Combines the current AnalysisResult with historical stats from GuidanceState
        to produce a complete snapshot the model can reason about.

        When result.overall is available (at rep milestones or end of session),
        includes a comprehensive overall rating with grade, trend, and suggestions.

        Returns a dict matching the coach context JSON schema.
        """
        # --- exercise ---
        exercise_en = self.EXERCISE_EN_MAP.get(self.exercise_name, self.exercise_name)
        exercise = {"cn": self.exercise_name, "en": exercise_en}

        # --- rep_count ---
        rep_count = result.count

        # --- phase (mapped to standard terminology) ---
        phase = self.PHASE_MAP.get(result.phase, result.phase)

        # --- score ---
        score = {
            "total": result.score.total,
            "angle": result.score.angle_score,
            "temporal": result.score.temporal_score,
            "symmetry": result.score.symmetry_score,
        }

        # --- overall_rating (when available) ---
        overall_rating = None
        if result.overall is not None:
            overall_rating = {
                "total_score": result.overall.total_score,
                "grade": result.overall.grade,
                "grade_emoji": result.overall.grade_emoji,
                "grade_message": result.overall.grade_message,
                "dimension_breakdown": result.overall.dimension_breakdown,
                "trend": result.overall.trend,
                "highlight": result.overall.highlight,
                "weakness": result.overall.weakness,
                "suggestion": result.overall.suggestion,
                "avg_angle_score": result.overall.avg_angle_score,
                "avg_temporal_score": result.overall.avg_temporal_score,
                "avg_symmetry_score": result.overall.avg_symmetry_score,
            }

        # --- joint_angles ---
        a = result.angles
        joint_angles = {
            "knee":    {"left": a.knee_left,    "right": a.knee_right},
            "hip":     {"left": a.hip_left,     "right": a.hip_right},
            "elbow":   {"left": a.elbow_left,   "right": a.elbow_right},
            "shoulder": {"left": a.shoulder_left, "right": a.shoulder_right},
            "trunk":   a.trunk_angle,
            "ankle":   {"left": a.ankle_left,   "right": a.ankle_right},
        }

        # --- errors ---
        errors = [
            {
                "name": err.name,
                "severity": err.severity,
                "suggestion": err.suggestion,
            }
            for err in result.errors
        ]

        # --- stats ---
        recent = self.state.recent_scores
        avg_recent = round(sum(recent) / len(recent), 1) if recent else 0.0
        # Build error ranking from accumulated counts
        error_ranking = dict(
            sorted(self.state.error_counts.items(), key=lambda x: x[1], reverse=True)
        )
        stats = {
            "best_score": round(self.state.best_score, 1),
            "avg_recent_score": avg_recent,
            "consecutive_good": self.state.consecutive_good_form,
            "consecutive_bad": self.state.consecutive_bad_form,
            "error_ranking": error_ranking,
        }

        result_dict = {
            "exercise": exercise,
            "rep_count": rep_count,
            "phase": phase,
            "score": score,
            "joint_angles": joint_angles,
            "errors": errors,
            "stats": stats,
        }
        if overall_rating is not None:
            result_dict["overall_rating"] = overall_rating
        return result_dict

    # ------------------------------------------------------------------
    # Cue 效果追踪 (Phase 4)
    # ------------------------------------------------------------------

    def record_cue(self, cue: str, tier: int, focus: str, target_error: str):
        """Record a correction cue that was sent to the user.

        Called after the LLM generates guidance — stores the cue for later
        effectiveness tracking. If the target error resolves within the
        resolve window, the cue is marked effective.

        Args:
            cue: The cue text sent to the user.
            tier: 1 (external), 2 (internal), or 3 (regression).
            focus: "external" / "internal" / "regression".
            target_error: The Chinese error name this cue targets.
        """
        self.state.cue_history.append({
            "cue": cue,
            "tier": tier,
            "focus": focus,
            "target_error": target_error,
            "timestamp": time.time(),
            "error_resolved": False,
            "frames_to_resolve": -1,
        })
        self.state.last_active_cues[target_error] = cue
        self.state._cue_frame_counters[cue] = 0

    def get_cue_effectiveness(self, target_error: str) -> dict | None:
        """Return effectiveness data for the most recent cue targeting an error.

        Returns None if no cue has been recorded for this error.
        """
        # Find the most recent cue for this error
        relevant = [c for c in self.state.cue_history
                    if c.get("target_error") == target_error]
        if not relevant:
            return None

        latest = relevant[-1]
        tried_cues = list(dict.fromkeys(  # dedup preserving order
            c["cue"] for c in relevant if not c.get("error_resolved", False)
        ))

        return {
            "last_cue": latest.get("cue", ""),
            "effective": latest.get("error_resolved", False),
            "tried_cues": tried_cues if not latest.get("error_resolved") else [],
            "frames_to_resolve": latest.get("frames_to_resolve", -1),
        }

    def get_all_cue_effectiveness(self) -> dict:
        """Return cue effectiveness for all tracked errors.

        Returns:
            {error_name: {last_cue, effective, tried_cues}}
        """
        # Group cues by target error
        by_error: dict[str, list[dict]] = {}
        for c in self.state.cue_history:
            target = c.get("target_error", "")
            if target not in by_error:
                by_error[target] = []
            by_error[target].append(c)

        result = {}
        for error_name, cues in by_error.items():
            latest = cues[-1]
            tried = list(dict.fromkeys(
                c["cue"] for c in cues if not c.get("error_resolved", False)
            ))
            result[error_name] = {
                "last_cue": latest.get("cue", ""),
                "effective": latest.get("error_resolved", False),
                "tried_cues": tried if not latest.get("error_resolved") else [],
            }
        return result

    def get_ineffective_cues(self, target_error: str) -> list[str]:
        """Return list of cue texts that were tried but didn't work for an error."""
        return [
            c["cue"] for c in self.state.cue_history
            if c.get("target_error") == target_error
            and not c.get("error_resolved", False)
        ]

    def reset(self):
        self.state = GuidanceState()
        self._last_guidance.clear()
        self._last_timestamp.clear()
