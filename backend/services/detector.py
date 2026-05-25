# backend/services/detector.py
import sys
from pathlib import Path
import numpy as np
import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.pose_analyzer import PoseAnalyzer, AnalysisResult, EXERCISE_STANDARDS
from code.guidance.context_engine import ContextEngine, GuidanceMessage

EXERCISE_LIST = list(EXERCISE_STANDARDS.keys())


class DetectorService:
    def __init__(self, model_path: str = "yolo26n-pose.pt"):
        self.model = YOLO(model_path)
        self.analyzer: PoseAnalyzer | None = None
        self.context_engine: ContextEngine | None = None
        self.current_exercise: str = "深蹲"

    def set_exercise(self, name: str):
        if name not in EXERCISE_STANDARDS:
            raise ValueError(f"Unsupported exercise: {name}")
        self.current_exercise = name
        self.analyzer = PoseAnalyzer(name)
        self.context_engine = ContextEngine(name)

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

        guidance = None
        if self.context_engine:
            msg = self.context_engine.process(analysis)
            if msg:
                guidance = {"type": msg.type.value, "text": msg.text, "priority": msg.priority}

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
        }

    def reset(self):
        self.analyzer = PoseAnalyzer(self.current_exercise)
        self.context_engine = ContextEngine(self.current_exercise)
