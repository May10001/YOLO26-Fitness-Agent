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
        if self.context_engine:
            msg = self.context_engine.process(analysis)
            if msg:
                guidance = {"type": msg.type.value, "text": msg.text, "priority": msg.priority}

            # Proactive LLM coach: check if a trigger should fire this frame
            if self.realtime_coach:
                trigger_context = self.realtime_coach.evaluate_frame(
                    analysis, self.context_engine.state, self.current_exercise
                )

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
                {"name": e.name, "severity": e.severity, "message": e.message, "suggestion": e.suggestion}
                for e in analysis.errors
            ],
            "guidance": guidance,
            "trigger_context": trigger_context,
            "heatmap": heatmap_data,
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

    def reset(self):
        self.analyzer = PoseAnalyzer(self.current_exercise)
        self.context_engine = ContextEngine(self.current_exercise)
        self.realtime_coach = RealTimeCoach()
        self.heatmap = JointAngleHeatmap(self.current_exercise)
        self._session_scores = []
