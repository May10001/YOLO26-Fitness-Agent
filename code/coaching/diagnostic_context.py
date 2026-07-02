"""
Diagnostic context builder — transforms raw pose data into structured diagnostic
data for LLM reasoning, plus two-stage output parsing and cue tracking support.

Phase 1: DiagnosticSnapshot + DiagnosticContextBuilder
Phase 3: CoachingOutput + CoachingOutputParser
Phase 4: Cue effectiveness feedback injection
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..pose_analyzer import AnalysisResult, ExerciseStandard


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class JointDeviation:
    """Per-joint deviation from standard."""
    joint_name: str            # "左膝" / "右膝" / "左髋" / ...
    current: float             # 当前值 (°)
    target: float              # 目标值 (°)
    deviation: float           # 偏差 = current - target
    status: str                # "不足" / "过度" / "标准" / "良好"
    history: list[float] = field(default_factory=list)  # 近 10 帧原始值
    std_dev: float = 0.0       # 滑动窗口内标准差 (°)，衡量该关节的稳定性
    stability: str = "稳定"    # "稳定" / "轻微波动" / "剧烈波动"


@dataclass
class AngleTrend:
    """Trend analysis for the primary joint angle."""
    direction: str             # "改善中" / "恶化中" / "稳定"
    slope: float               # deg/frame 趋势斜率
    recent_values: list[float] = field(default_factory=list)  # 近 10 帧


@dataclass
class CooccurrencePattern:
    """Co-occurring error pattern with interpretation."""
    errors: list[str]          # 同时出现的错误名
    interpretation: str        # 共现含义（从知识库查询）


@dataclass
class DiagnosticSnapshot:
    """Complete diagnostic snapshot for one frame.

    Replaces raw angle dump — every joint comes with target, deviation,
    and trend context so the LLM can reason about *why* scores are low.
    """
    # Per-joint deviations (replaces raw angle values)
    joint_deviations: dict[str, JointDeviation] = field(default_factory=dict)
    # Trend of the primary angle
    angle_trend: Optional[AngleTrend] = None
    # Per-dimension trend labels
    score_trends: dict[str, str] = field(default_factory=dict)
    # Co-occurring error patterns
    error_cooccurrence: list[CooccurrencePattern] = field(default_factory=list)
    # Which dimension is dragging the total down and why
    dimension_diagnosis: str = ""


# ============================================================================
# Context builder
# ============================================================================

class DiagnosticContextBuilder:
    """Builds diagnostic context from AnalysisResult + MovementScorer internals.

    Takes raw pose data and scorer state and produces a DiagnosticSnapshot
    that captures deviations, trends, and co-occurrence — everything the LLM
    needs to reason biomechanically instead of just reading numbers.
    """

    # Joint name mappings for display
    _JOINT_CN = {
        "knee_left": "左膝", "knee_right": "右膝",
        "hip_left": "左髋", "hip_right": "右髋",
        "elbow_left": "左肘", "elbow_right": "右肘",
        "shoulder_left": "左肩", "shoulder_right": "右肩",
        "trunk": "躯干",
        "ankle_left": "左踝", "ankle_right": "右踝",
    }

    # Status thresholds relative to target
    _STATUS_EXCELLENT = 5.0    # within ±5° → "标准"
    _STATUS_GOOD = 12.5        # within ±12.5° → "良好"
    # beyond → "不足" or "过度"

    @classmethod
    def build(cls,
              analysis_result: AnalysisResult,
              scorer_data: dict,
              exercise_name: str) -> DiagnosticSnapshot:
        """Build a DiagnosticSnapshot from one frame's data.

        Args:
            analysis_result: The per-frame AnalysisResult from PoseAnalyzer.
            scorer_data: Dict from MovementScorer.get_diagnostic_data().
            exercise_name: Chinese exercise name.

        Returns:
            DiagnosticSnapshot ready for LLM formatting.
        """
        standard = scorer_data.get("_standard")
        phase = analysis_result.phase

        # 1. Per-joint deviations
        joint_deviations = cls._build_joint_deviations(
            analysis_result, scorer_data, standard, phase
        )

        # 2. Primary angle trend
        angle_trend = cls._build_angle_trend(scorer_data)

        # 3. Score dimension trends
        score_trends = cls._build_score_trends(scorer_data)

        # 4. Co-occurrence patterns
        error_cooccurrence = cls._build_cooccurrence(
            analysis_result, exercise_name
        )

        # 5. Dimension diagnosis
        dimension_diagnosis = cls._build_dimension_diagnosis(analysis_result)

        return DiagnosticSnapshot(
            joint_deviations=joint_deviations,
            angle_trend=angle_trend,
            score_trends=score_trends,
            error_cooccurrence=error_cooccurrence,
            dimension_diagnosis=dimension_diagnosis,
        )

    # ------------------------------------------------------------------
    # Per-joint deviations
    # ------------------------------------------------------------------

    # Stability thresholds for std_dev interpretation
    _STD_STABLE = 3.0        # ≤3° → "稳定"
    _STD_MILD = 7.0          # ≤7° → "轻微波动", >7° → "剧烈波动"

    @classmethod
    def _build_joint_deviations(cls,
                                 result: AnalysisResult,
                                 scorer_data: dict,
                                 standard,
                                 phase: str) -> dict[str, JointDeviation]:
        """Compute per-joint deviation against standard targets.

        Uses per-joint history for:
        - history: last 10 raw values of *this* joint (not the primary angle)
        - std_dev: sliding-window standard deviation → joint stability metric
        - stability: human-readable stability label
        """
        deviations = {}
        a = result.angles

        # Per-joint angle history (from MovementScorer, populated in update_symmetry)
        per_joint_history = scorer_data.get("per_joint_history", {})

        # Map each joint to (current_value, target_value)
        joint_targets = cls._get_joint_targets(a, standard, phase)

        for joint_key, (current_val, target_val) in joint_targets.items():
            if current_val is None:
                continue

            cn_name = cls._JOINT_CN.get(joint_key, joint_key)
            dev = current_val - target_val

            # Determine status
            abs_dev = abs(dev)
            if abs_dev <= cls._STATUS_EXCELLENT:
                status = "标准"
            elif abs_dev <= cls._STATUS_GOOD:
                status = "良好"
            elif dev > 0:
                status = "过度"
            else:
                status = "不足"

            # Per-joint history (this joint's own values, not the primary angle)
            joint_history = per_joint_history.get(joint_key, [])
            recent_history = joint_history[-10:] if joint_history else []

            # Sliding-window standard deviation
            std_dev = 0.0
            stability_label = "稳定"
            if len(joint_history) >= 5:
                window = joint_history[-15:]  # last ~0.5s at 30fps
                std_dev = float(np.std(window))
                if std_dev <= cls._STD_STABLE:
                    stability_label = "稳定"
                elif std_dev <= cls._STD_MILD:
                    stability_label = "轻微波动"
                else:
                    stability_label = "剧烈波动"

            deviations[joint_key] = JointDeviation(
                joint_name=cn_name,
                current=round(current_val, 1),
                target=round(target_val, 1),
                deviation=round(dev, 1),
                status=status,
                history=[round(h, 1) for h in recent_history],
                std_dev=round(std_dev, 1),
                stability=stability_label,
            )

        return deviations

    @classmethod
    def _get_joint_targets(cls, angles, standard,
                           phase: str) -> dict[str, tuple[Optional[float], float]]:
        """Determine the target value for each joint angle.

        For the primary joint, target depends on phase. For trunk, target
        is 0° (vertical). For symmetry joints, target is 0° difference.
        For secondary joints, target is the standard range midpoint.
        """
        targets = {}

        if standard is None:
            # Fallback: use sensible defaults
            for attr in ["knee", "hip", "elbow", "shoulder"]:
                for side in ["left", "right"]:
                    key = f"{attr}_{side}"
                    val = getattr(angles, key, None)
                    targets[key] = (val, 90.0)  # default target
            if angles.trunk_angle is not None:
                targets["trunk"] = (angles.trunk_angle, 0.0)
            return targets

        primary = standard.primary_joint
        # Determine target for the primary joint based on phase
        if phase in ("低位", "保持"):
            primary_target = standard.target_low
        else:
            primary_target = standard.target_high

        # Map primary_joint name to the attribute names
        # primary_joint is like "knee_angle", we need "knee_left"/"knee_right"
        primary_base = primary.replace("_angle", "")

        for attr in ["knee", "hip", "elbow", "shoulder"]:
            for side in ["left", "right"]:
                key = f"{attr}_{side}"
                val = getattr(angles, key, None)
                if val is not None:
                    if attr == primary_base:
                        targets[key] = (val, primary_target)
                    else:
                        # Secondary joints: use range midpoint as target
                        targets[key] = (val, primary_target)

        # Trunk — target is 0° (standing vertical) or trunk_max for exercises
        # where some trunk lean is expected
        if angles.trunk_angle is not None:
            trunk_target = standard.trunk_max / 2.0  # midpoint of allowed range
            targets["trunk"] = (angles.trunk_angle, trunk_target)

        # Ankle — no standard target, use 90° as neutral
        for side in ["left", "right"]:
            key = f"ankle_{side}"
            val = getattr(angles, key, None)
            if val is not None:
                targets[key] = (val, 90.0)

        return targets

    # ------------------------------------------------------------------
    # Angle trend (linear regression on recent frames)
    # ------------------------------------------------------------------

    @classmethod
    def _build_angle_trend(cls, scorer_data: dict) -> Optional[AngleTrend]:
        """Compute trend of the primary angle from recent records."""
        angle_records = scorer_data.get("angle_records", [])
        if len(angle_records) < 5:
            return None

        # Take last 15 records (or all if fewer)
        recent = angle_records[-15:]
        values = [rec[0] for rec in recent]  # smoothed angles

        if len(values) < 5:
            return None

        # Simple linear regression: value = slope * i + intercept
        n = len(values)
        x = np.arange(n)
        y = np.array(values)
        x_mean = x.mean()
        y_mean = y.mean()
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)
        if abs(denominator) < 1e-9:
            slope = 0.0
        else:
            slope = float(numerator / denominator)

        # Direction with hysteresis (avoid flickering on noise)
        if slope > 0.3:
            direction = "改善中"  # moving toward target
        elif slope < -0.3:
            direction = "恶化中"
        else:
            direction = "稳定"

        return AngleTrend(
            direction=direction,
            slope=round(slope, 3),
            recent_values=[round(v, 1) for v in values[-10:]],
        )

    # ------------------------------------------------------------------
    # Score dimension trends
    # ------------------------------------------------------------------

    @classmethod
    def _build_score_trends(cls, scorer_data: dict) -> dict[str, str]:
        """Compute per-dimension trend from score history."""
        score_history = scorer_data.get("score_history", {})
        trends = {}

        for dim, key in [("angle", "angle"), ("temporal", "temporal"),
                         ("symmetry", "symmetry")]:
            history = score_history.get(key, [])
            if len(history) < 6:
                trends[dim] = "稳定"
                continue

            early = np.mean(history[:3])
            late = np.mean(history[-3:])
            diff = late - early

            if diff > 2:
                trends[dim] = "上升"
            elif diff < -2:
                trends[dim] = "下降"
            else:
                trends[dim] = "稳定"

        return trends

    # ------------------------------------------------------------------
    # Co-occurrence patterns
    # ------------------------------------------------------------------

    @classmethod
    def _build_cooccurrence(cls,
                             result: AnalysisResult,
                             exercise_name: str) -> list[CooccurrencePattern]:
        """Detect co-occurring error patterns and look up interpretations."""
        if len(result.errors) < 2:
            return []

        error_names = [e.name for e in result.errors]

        # Known co-occurrence patterns with biomechanical interpretations
        KNOWN_PATTERNS = {
            ("膝盖内扣", "深蹲弓背"): "膝内扣 + 弓背 → 臀中肌薄弱 + 核心不稳，髋关节稳定性不足导致膝关节代偿",
            ("俯卧撑塌腰", "肘部外展"): "塌腰 + 肘外展 → 核心失稳 + 肩胛控制不足，躯干无法维持刚性",
            ("身体晃动", "肘部外展"): "晃动 + 肘外展 → 核心稳定不足 + 肩带肌群控制差，力量链断裂",
            ("肩推弓背", "肘部外展"): "弓背 + 肘外展 → 核心支撑不足，腰椎过度伸展代偿肩部力量不足",
            ("身体后仰", "膝盖内扣"): "后仰 + 膝内扣 → 核心与髋关节双重失稳，骨盆控制能力薄弱",
        }

        patterns = []
        # Check all 2-error combinations
        for i in range(len(error_names)):
            for j in range(i + 1, len(error_names)):
                pair = (error_names[i], error_names[j])
                rev_pair = (error_names[j], error_names[i])
                interpretation = KNOWN_PATTERNS.get(pair) or KNOWN_PATTERNS.get(rev_pair)
                if interpretation:
                    patterns.append(CooccurrencePattern(
                        errors=list(pair),
                        interpretation=interpretation,
                    ))

        return patterns

    # ------------------------------------------------------------------
    # Dimension diagnosis
    # ------------------------------------------------------------------

    @classmethod
    def _build_dimension_diagnosis(cls, result: AnalysisResult) -> str:
        """Identify which dimension is dragging the total down."""
        score = result.score
        dims = [
            ("关节角度", score.angle_score, 40.0),
            ("时序节奏", score.temporal_score, 30.0),
            ("左右对称", score.symmetry_score, 30.0),
        ]

        # Sort by percentage score ascending (worst first)
        dims.sort(key=lambda x: x[1] / x[2])

        worst_name, worst_score, worst_max = dims[0]
        pct = worst_score / worst_max * 100

        if pct >= 85:
            return "各维度表现均衡，无明显短板"
        elif pct >= 70:
            return f"{worst_name}维度略低（{worst_score:.0f}/{worst_max:.0f}），建议针对性改善"
        elif pct >= 50:
            return f"{worst_name}维度明显偏低（{worst_score:.0f}/{worst_max:.0f}），需重点改进"
        else:
            return f"{worst_name}维度严重不足（{worst_score:.0f}/{worst_max:.0f}），应从基础动作模式开始纠正"

    # ------------------------------------------------------------------
    # Formatting for LLM context
    # ------------------------------------------------------------------

    @classmethod
    def format_for_llm(cls,
                       snapshot: DiagnosticSnapshot,
                       biomechanics: dict | None = None,
                       cue_effectiveness: dict | None = None) -> str:
        """Format the diagnostic snapshot as a Chinese text block for LLM prompts.

        Args:
            snapshot: The DiagnosticSnapshot to format.
            biomechanics: Optional biomechanical KB for the current exercise.
            cue_effectiveness: Optional cue tracking feedback dict.
        """
        lines = []

        # --- 关节角度诊断 ---
        lines.append("【关节角度诊断】")
        if snapshot.joint_deviations:
            for key, jd in snapshot.joint_deviations.items():
                hist_str = ""
                if jd.history:
                    hist_vals = ", ".join(f"{v:.0f}°" for v in jd.history[-5:])
                    hist_str = f" | 近5帧: [{hist_vals}]"
                # Stability annotation: helps LLM distinguish "wrong but stable" from "wrong and erratic"
                stab_str = f" | σ={jd.std_dev:.1f}° ({jd.stability})"
                lines.append(
                    f"{jd.joint_name}: {jd.current:.0f}° "
                    f"(目标 {jd.target:.0f}°, 偏差 {jd.deviation:+.0f}°, "
                    f"状态: {jd.status}){stab_str}{hist_str}"
                )
        else:
            lines.append("暂无角度数据")

        # --- 趋势分析 ---
        lines.append("")
        lines.append("【趋势分析】")
        if snapshot.angle_trend:
            at = snapshot.angle_trend
            vals_str = ", ".join(f"{v:.0f}°" for v in at.recent_values[-5:])
            lines.append(
                f"关键角度趋势: {at.direction}（斜率 {at.slope:+.3f}°/帧）"
            )
            lines.append(f"近5帧: [{vals_str}]")
        else:
            lines.append("数据不足，暂无法分析趋势")

        if snapshot.score_trends:
            trend_labels = []
            for dim, trend in snapshot.score_trends.items():
                dim_cn = {"angle": "角度", "temporal": "时序", "symmetry": "对称"}.get(dim, dim)
                trend_labels.append(f"{dim_cn}: {trend}")
            lines.append("分维度趋势: " + " | ".join(trend_labels))

        # --- 维度诊断 ---
        lines.append("")
        lines.append("【维度诊断】")
        lines.append(snapshot.dimension_diagnosis)

        # --- 共现模式 ---
        if snapshot.error_cooccurrence:
            lines.append("")
            lines.append("【共现模式】")
            for cp in snapshot.error_cooccurrence:
                errors_str = " + ".join(cp.errors)
                lines.append(f"{errors_str} → {cp.interpretation}")

        # --- 生物力学知识（从知识库注入） ---
        if biomechanics:
            lines.append("")
            lines.append("【生物力学知识】")
            for error_name, kb in biomechanics.items():
                lines.append(f"\n◆ {error_name}:")
                # Root cause chains
                chains = kb.get("root_cause_chain", [])
                if chains:
                    lines.append("  根因链:")
                    for i, chain in enumerate(chains, 1):
                        lines.append(f"    {i}. {chain}")
                # Top-tier external cues
                cues = kb.get("correction_cues", {})
                tier1 = cues.get("tier1_external", [])
                if tier1:
                    lines.append("  首选纠正 cue (Tier 1 外部注意力):")
                    for c in tier1[:2]:  # Only top 2 to save tokens
                        lines.append(f"    • {c.get('cue', c)}")
                tier2 = cues.get("tier2_internal", [])
                if tier2:
                    lines.append("  备选纠正 cue (Tier 2 内部注意力):")
                    for c in tier2[:1]:
                        lines.append(f"    • {c.get('cue', c)}")
                tier3 = cues.get("tier3_regression", [])
                if tier3:
                    lines.append("  回归训练 (Tier 3):")
                    for c in tier3[:1]:
                        lines.append(f"    • {c.get('exercise', c)}")

        # --- 上次指导效果（cue 追踪反馈） ---
        if cue_effectiveness:
            lines.append("")
            lines.append("【上次指导效果】")
            for error_name, effect in cue_effectiveness.items():
                last_cue = effect.get("last_cue", "")
                effective = effect.get("effective", True)
                tried = effect.get("tried_cues", [])
                if effective:
                    lines.append(f"{error_name}: 上次提示\"{last_cue}\"→ 效果良好，错误已改善")
                else:
                    tried_str = "、".join(tried[-3:]) if tried else last_cue
                    lines.append(f"{error_name}: 上次提示\"{last_cue}\"→ 效果不佳（错误仍持续）")
                    lines.append(f"  已尝试过的 cue: {tried_str} → 请尝试不同 cue 角度或升级 Tier")

        return "\n".join(lines)

    @classmethod
    def format_json(cls, snapshot: DiagnosticSnapshot) -> dict:
        """Serialize DiagnosticSnapshot to a JSON-safe dict for LangGraph state."""
        result = {
            "joint_deviations": {},
            "angle_trend": None,
            "score_trends": snapshot.score_trends,
            "error_cooccurrence": [],
            "dimension_diagnosis": snapshot.dimension_diagnosis,
        }

        for key, jd in snapshot.joint_deviations.items():
            result["joint_deviations"][key] = {
                "joint_name": jd.joint_name,
                "current": jd.current,
                "target": jd.target,
                "deviation": jd.deviation,
                "status": jd.status,
                "history": jd.history,
                "std_dev": jd.std_dev,
                "stability": jd.stability,
            }

        if snapshot.angle_trend:
            result["angle_trend"] = {
                "direction": snapshot.angle_trend.direction,
                "slope": snapshot.angle_trend.slope,
                "recent_values": snapshot.angle_trend.recent_values,
            }

        for cp in snapshot.error_cooccurrence:
            result["error_cooccurrence"].append({
                "errors": cp.errors,
                "interpretation": cp.interpretation,
            })

        return result


# ============================================================================
# Two-stage output parsing (Phase 3)
# ============================================================================

@dataclass
class CoachingOutput:
    """Parsed two-stage LLM output."""
    diagnosis: dict            # Parsed diagnosis JSON (empty dict if parse failed)
    guidance: str              # User-facing guidance text
    raw_response: str          # Original LLM response (for fallback / debugging)


class CoachingOutputParser:
    """Parses LLM output in <diagnosis>...</diagnosis><guidance>...</guidance> format.

    Gracefully degrades: if the tags can't be parsed, the entire response
    becomes the guidance text and diagnosis is left empty.
    """

    DIAGNOSIS_RE = re.compile(r'<diagnosis>\s*(.*?)\s*</diagnosis>', re.DOTALL | re.IGNORECASE)
    GUIDANCE_RE = re.compile(r'<guidance>\s*(.*?)\s*</guidance>', re.DOTALL | re.IGNORECASE)

    @classmethod
    def parse(cls, raw_text: str) -> CoachingOutput:
        """Parse a two-stage LLM response.

        Args:
            raw_text: The raw LLM output string.

        Returns:
            CoachingOutput with diagnosis dict and guidance string.
            If parsing fails, diagnosis is empty dict and guidance = raw_text.
        """
        if not raw_text:
            return CoachingOutput(
                diagnosis={},
                guidance="",
                raw_response="",
            )

        # Extract diagnosis JSON
        diag_match = cls.DIAGNOSIS_RE.search(raw_text)
        diagnosis = {}
        if diag_match:
            try:
                diagnosis = json.loads(diag_match.group(1).strip())
            except json.JSONDecodeError:
                # Try to salvage — sometimes the JSON is not valid but close
                diagnosis = {"raw_diagnosis": diag_match.group(1).strip()}

        # Extract guidance text
        guide_match = cls.GUIDANCE_RE.search(raw_text)
        if guide_match:
            guidance = guide_match.group(1).strip()
        else:
            # Fallback: strip any diagnosis block and use the rest
            guidance = cls.DIAGNOSIS_RE.sub('', raw_text).strip()
            if not guidance:
                guidance = raw_text.strip()

        return CoachingOutput(
            diagnosis=diagnosis,
            guidance=guidance,
            raw_response=raw_text,
        )

    @classmethod
    def extract_cues(cls, diagnosis: dict) -> list[dict]:
        """Extract recommended cues from the diagnosis JSON for tracking.

        Handles various shapes the LLM might produce:
        - {"recommended_cues": [{"cue": "...", "tier": 1, "focus": "external"}]}
        - {"recommended_cues": ["cue text 1", "cue text 2"]}  (simple list)
        """
        cues = diagnosis.get("recommended_cues", [])
        if not cues:
            return []

        result = []
        for c in cues:
            if isinstance(c, dict):
                result.append({
                    "cue": c.get("cue", str(c)),
                    "tier": c.get("tier", 1),
                    "focus": c.get("focus", "unknown"),
                })
            elif isinstance(c, str):
                result.append({"cue": c, "tier": 1, "focus": "unknown"})
        return result
