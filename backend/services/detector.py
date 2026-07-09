# backend/services/detector.py
import sys
from pathlib import Path
import numpy as np
import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.pose_analyzer import PoseAnalyzer, AnalysisResult, EXERCISE_STANDARDS
from code.guidance.context_engine import ContextEngine, GuidanceMessage
from code.realtime_coach import RealTimeCoach
from code.visualization import JointAngleHeatmap, JOINT_DISPLAY_NAMES

EXERCISE_LIST = list(EXERCISE_STANDARDS.keys())


class DetectorService:
    def __init__(self, model_path: str = "yolo26n-pose.pt"):
        self.model = YOLO(model_path)
        self.analyzer: PoseAnalyzer | None = None
        self.context_engine: ContextEngine | None = None
        self.realtime_coach: RealTimeCoach | None = None
        self.heatmap: JointAngleHeatmap | None = None
        self.current_exercise: str = "深蹲"
        # Per-session score tracking (used by session/stop for history)
        self._session_scores: list[float] = []

    def set_exercise(self, name: str):
        if name not in EXERCISE_STANDARDS:
            raise ValueError(f"Unsupported exercise: {name}")
        self.current_exercise = name
        self.analyzer = PoseAnalyzer(name)
        self.context_engine = ContextEngine(name)
        self.realtime_coach = RealTimeCoach()
        self.heatmap = JointAngleHeatmap(name)
        self._session_scores = []

    def process_frame(self, frame: np.ndarray) -> dict:
        if self.analyzer is None:
            self.set_exercise(self.current_exercise)

        results = self.model(frame, verbose=False)
        if not results or len(results[0].keypoints) == 0:
            return {"detected": False}

        kp_data = results[0].keypoints[0]
        keypoints = kp_data.xy[0].cpu().numpy()
        confidences = kp_data.conf[0].cpu().numpy() if kp_data.conf is not None else None

        analysis = self.analyzer.analyze_frame(keypoints, confidences)

        # Track scores for session history
        if analysis.score.total > 0:
            self._session_scores.append(analysis.score.total)

        # Record angles for joint heatmap
        if self.heatmap:
            self.heatmap.record_frame(analysis.angles)

        guidance = None
        trigger_context = None
        trigger_type = "proactive"
        if self.context_engine:
            msg = self.context_engine.process(analysis)
            if msg:
                guidance = {"type": msg.type.value, "text": msg.text, "priority": msg.priority}

            # Proactive LLM coach: check if a trigger should fire this frame
            if self.realtime_coach:
                trigger_event = self.realtime_coach.evaluate_frame(
                    analysis, self.context_engine.state, self.current_exercise
                )
                if trigger_event:
                    trigger_context = trigger_event.context
                    trigger_type = trigger_event.type.value

        # Build joint heatmap deviation data
        heatmap_data = None
        if self.heatmap:
            matrix = self.heatmap.compute_deviation_matrix()
            if matrix:
                import math as _m
                heatmap_data = {
                    "joints": [
                        {
                            "key": k,
                            "name": JOINT_DISPLAY_NAMES.get(k, k),
                            "user_avg": v["user_avg"],
                            "standard_mid": v["standard_mid"],
                            "deviation": v["deviation"],
                            "deviation_ratio": v["deviation_ratio"],
                            "severity": v["severity"],
                        }
                        for k, v in matrix.items()
                    ],
                }

        # --- Cue effectiveness tracking (Phase 4: exposed to frontend) ---
        cue_tracking = None
        if self.context_engine:
            all_cues = self.context_engine.get_all_cue_effectiveness()
            if all_cues:
                active_cues = []
                for err_name, eff in all_cues.items():
                    if not eff.get("effective", True):
                        active_cues.append({
                            "error_name": err_name,
                            "last_cue": eff.get("last_cue", ""),
                            "effective": False,
                            "tried_cues": eff.get("tried_cues", []),
                        })
                if active_cues:
                    cue_tracking = {"active_cues": active_cues}

        # --- Debug: expose raw scoring internals for the frontend debug overlay ---
        std = self.analyzer.standard if self.analyzer else None
        angles = analysis.angles
        temporal = analysis.temporal
        primary_angle = angles.primary_angle(self.current_exercise) if angles else None

        # Dynamic target (same logic as MovementScorer._dynamic_target)
        if std and primary_angle is not None:
            phase = analysis.phase
            low_min, low_max = std.low_range
            high_min, high_max = std.high_range
            if phase in ("低位", "保持"):
                if low_min <= primary_angle <= low_max:
                    target_angle = primary_angle  # 范围内 → 合标
                elif low_max < primary_angle < high_min:
                    target_angle = primary_angle  # 过渡区 → 不罚
                else:
                    target_angle = std.target_low   # 超范围 → 惩罚
            else:
                if high_min <= primary_angle <= high_max:
                    target_angle = primary_angle  # 范围内 → 合标
                elif low_max < primary_angle < high_min:
                    target_angle = primary_angle  # 过渡区 → 不罚
                else:
                    target_angle = std.target_high  # 超范围 → 惩罚
        else:
            target_angle = None

        # Knee symmetry (for squat: primary joint is knee)
        knee_diff = angles.diff_symmetric("knee") if angles else None

        debug_info = {
            "primary_angle": round(primary_angle, 1) if primary_angle is not None else None,
            "knee_left": round(angles.knee_left, 1) if angles and angles.knee_left is not None else None,
            "knee_right": round(angles.knee_right, 1) if angles and angles.knee_right is not None else None,
            "target_angle": round(target_angle, 1) if target_angle is not None else None,
            "deviation": round(abs(primary_angle - target_angle), 1)
                         if primary_angle is not None and target_angle is not None else None,
            "knee_diff": round(knee_diff, 1) if knee_diff is not None else None,
            "symmetry_max_diff": std.symmetry_max_diff if std else None,
            "temporal_rhythm_cv": round(temporal.rhythm_consistency, 3),
            "temporal_smoothness": round(temporal.smoothness, 1),
            "angular_velocity": round(temporal.angular_velocity, 1),
        }

        # --- Diagnostic snapshot (per-joint σ, angle trend, dimension diagnosis) ---
        diagnostic_snapshot = None
        if self.analyzer and self.analyzer._scorer:
            scorer = self.analyzer._scorer
            scorer_data = scorer.get_diagnostic_data()
            if scorer_data:
                try:
                    from code.coaching.diagnostic_context import DiagnosticContextBuilder
                    snapshot = DiagnosticContextBuilder.build(
                        analysis, scorer_data, self.current_exercise
                    )
                    # Serialize to JSON-compatible dict
                    diag_dict: dict = {
                        "joint_deviations": [],
                        "angle_trend": None,
                        "dimension_diagnosis": snapshot.dimension_diagnosis,
                        "error_cooccurrence": [],
                    }
                    for key, jd in snapshot.joint_deviations.items():
                        diag_dict["joint_deviations"].append({
                            "joint_name": jd.joint_name,
                            "current": jd.current,
                            "target": jd.target,
                            "deviation": jd.deviation,
                            "status": jd.status,
                            "std_dev": jd.std_dev,
                            "stability": jd.stability,
                        })
                    if snapshot.angle_trend:
                        diag_dict["angle_trend"] = {
                            "direction": snapshot.angle_trend.direction,
                            "slope": snapshot.angle_trend.slope,
                            "recent_values": snapshot.angle_trend.recent_values,
                        }
                    for cp in snapshot.error_cooccurrence:
                        diag_dict["error_cooccurrence"].append({
                            "errors": cp.errors,
                            "interpretation": cp.interpretation,
                        })
                    diagnostic_snapshot = diag_dict
                except Exception:
                    diagnostic_snapshot = None

        return {
            "detected": True,
            "keypoints": keypoints.tolist(),
            "score": {
                "total": analysis.score.total,
                "angle": analysis.score.angle_score,
                "temporal": analysis.score.temporal_score,
                "symmetry": analysis.score.symmetry_score,
            },
            "phase": analysis.phase,
            "count": analysis.count,
            "hold_time": analysis.hold_time,
            "errors": [
                {"name": e.name, "severity": e.severity, "message": e.message, "suggestion": e.suggestion, "joints": e.affected_joints}
                for e in analysis.errors
            ],
            "guidance": guidance,
            "trigger_context": trigger_context,
            "trigger_type": trigger_type,
            "heatmap": heatmap_data,
            "cue_tracking": cue_tracking,
            "debug": debug_info,
            "diagnostic_snapshot": diagnostic_snapshot,
        }

    def get_session_stats(self) -> dict:
        """Return accumulated session statistics for training history."""
        scores = self._session_scores
        return {
            "total_reps": self.analyzer.count if self.analyzer else 0,
            "best_score": round(float(np.max(scores)), 1) if scores else 0.0,
            "avg_score": round(float(np.mean(scores)), 1) if scores else 0.0,
            "error_counts": getattr(self.analyzer, '_error_detector', None) and dict(self.analyzer._error_detector._error_counter) or {},
        }

    def apply_tuning(self, params: dict):
        """运行时调参 — 同步更新 PoseAnalyzer 和其内部 Scorer."""
        if self.analyzer:
            self.analyzer.apply_tuning(**params)

    def get_tuning_params(self) -> dict:
        """返回当前可调参数值, 供前端初始化滑块."""
        if not self.analyzer:
            return {}
        std = self.analyzer.standard
        scorer = self.analyzer._scorer
        return {
            "target_low": std.target_low,
            "target_high": std.target_high,
            "symmetry_max_diff": std.symmetry_max_diff,
            "angle_tolerance": scorer.angle_tolerance,
            "smooth_alpha": scorer.smooth_alpha,
        }

    def reset(self):
        self.analyzer = PoseAnalyzer(self.current_exercise)
        self.context_engine = ContextEngine(self.current_exercise)
        self.realtime_coach = RealTimeCoach()
        self.heatmap = JointAngleHeatmap(self.current_exercise)
        self._session_scores = []
