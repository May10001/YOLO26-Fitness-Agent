"""
YOLO26 居家健身实时交互监控系统
================================
C成员第二阶段 — 统一健身应用

功能:
  1. 集成 PoseAnalyzer + ContextEngine 动作评估模块
  2. 多线程分离检测与渲染 (目标 ≥30fps)
  3. 开始/暂停/继续/停止 + 切换动作 + 历史记录
  4. 离线运行模式 (本地 YOLO + Qwen2.5 模型)
"""

import argparse
import json
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk
from ultralytics import YOLO

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _PROJECT_ROOT)
# 移除脚本自身目录, 避免屏蔽 code 包 (python code/workout_app.py 时发生)
_script_dir = str(Path(__file__).resolve().parent)
if _script_dir in sys.path:
    sys.path.remove(_script_dir)
# cv2/numpy/ultralytics 等库会间接导入 stdlib 的 code 模块,
# 导致 "code is not a package" 错误, 需从 sys.modules 中移除
if "code" in sys.modules:
    del sys.modules["code"]
from code.pose_analyzer import (
    PoseAnalyzer, JointAngles, AnalysisResult,
    EXERCISE_STANDARDS, JointAngleExtractor
)
from code.guidance.context_engine import ContextEngine, GuidanceMessage
from code.visualization import JointAngleHeatmap
from code.coach_system_prompt import COACH_SYSTEM_PROMPT, COACH_SYSTEM_PROMPT_PROACTIVE
from code.realtime_coach import RealTimeCoach

try:
    from code.models.base_model import BaseModel
    _BASE_MODEL_AVAILABLE = True
except ImportError:
    _BASE_MODEL_AVAILABLE = False
    BaseModel = None


# ============================================================================
# 常量定义
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "yolo26n-pose.pt"
HISTORY_DIR = BASE_DIR / "data" / "training_history"

# Model size options for the chat assistant (mirrors BaseModel.MODEL_VARIANTS)
CHAT_MODEL_SIZES = ["0.5B", "1.5B", "3B", "7B"]
CHAT_DEFAULT_MODEL_SIZE = "0.5B"

KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

SKELETON = [
    (5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12),
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
]

SIDE_KEYPOINTS = {
    "左侧": {
        "elbow": (5, 7, 9), "knee": (11, 13, 15),
        "hip": (5, 11, 13), "shoulder": (7, 5, 11),
    },
    "右侧": {
        "elbow": (6, 8, 10), "knee": (12, 14, 16),
        "hip": (6, 12, 14), "shoulder": (8, 6, 12),
    },
}

EXERCISE_ENGLISH_NAMES = {
    "深蹲": "squat", "俯卧撑": "push-up", "平板支撑": "plank",
    "卷腹": "crunch", "开合跳": "jumping jack", "引体向上": "pull-up",
    "臀桥": "glute bridge", "高抬腿": "high knees", "肩推": "shoulder press",
    "侧平举": "lateral raise",
}

PHASE_ENGLISH_NAMES = {"等待": "waiting", "低位": "low", "高位": "high", "保持": "hold"}

ALL_EXERCISES = list(EXERCISE_STANDARDS.keys())

CHAT_SYSTEM_PROMPT = (
    "你是一个专业的AI健身助手教练，拥有运动科学、运动解剖学和营养学背景。"
    "你的核心职责：\n"
    "1. 根据用户正在进行的健身动作，提供专业的动作要领指导、常见错误姿势纠正和呼吸节奏建议。\n"
    "2. 解答关于力量训练、有氧运动、增肌减脂、营养饮食、运动恢复等健身相关问题。\n"
    "3. 根据用户的训练目标和当前水平，给出个性化的训练计划建议。\n"
    "4. 用积极鼓励的语气帮助用户建立健身信心，同时提醒运动安全注意事项。\n"
    "5. 如果用户询问与健身运动完全无关的话题，请委婉引导回健身领域。\n\n"
    "回复风格：简洁专业、亲切友好、富有鼓励性。每次回复控制在3-5句话，"
    "必要时可分点说明。使用用户提问的语言进行回复。"
)

CHAT_WELCOME = (
    "🏋️ 你好！我是你的AI健身助手，基于本地 Qwen2.5。\n"
    "我可以帮你：\n"
    "  · 指导动作要领，纠正错误姿势\n"
    "  · 制定个性化训练计划\n"
    "  · 解答增肌、减脂、营养等问题\n"
    "  · 在你运动时提供实时建议\n\n"
    "请在下方输入你的问题，开始我们的健身之旅吧！"
)


# ============================================================================
# 几何辅助函数
# ============================================================================

def calculate_angle(a, b, c):
    a, b, c = np.asarray(a, np.float32), np.asarray(b, np.float32), np.asarray(c, np.float32)
    rad = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
    angle = abs(rad * 180.0 / math.pi)
    return 360.0 - angle if angle > 180.0 else angle


def valid_point(kp, conf, idx, min_conf=0.15):
    if idx >= len(kp):
        return False
    x, y = kp[idx]
    if x <= 0 and y <= 0:
        return False
    if conf is not None and conf[idx] < min_conf:
        return False
    return True


def side_angle(kp, conf, joint_name, side):
    ids = SIDE_KEYPOINTS[side][joint_name]
    if all(valid_point(kp, conf, i) for i in ids):
        return calculate_angle(kp[ids[0]], kp[ids[1]], kp[ids[2]])
    return None


# ============================================================================
# 检测结果数据结构
# ============================================================================

@dataclass
class DetectionResult:
    """检测线程产出的单帧结果."""
    frame: np.ndarray
    analysis: Optional[AnalysisResult] = None
    guidance: Optional[GuidanceMessage] = None
    fps: float = 0.0
    keypoints_detected: bool = False


# ============================================================================
# 检测线程
# ============================================================================

class DetectionThread(threading.Thread):
    """独立检测线程: 摄像头读取 → YOLO推理 → PoseAnalyzer → ContextEngine → 绘图.

    通过 queue.Queue 将结果发送给主线程, 实现检测与渲染分离.
    """

    def __init__(self, model_path: str, camera_index: int, confidence: float,
                 exercise_name: str, mirror: bool, show_skeleton: bool,
                 show_labels: bool, result_queue: queue.Queue):
        super().__init__(daemon=True)
        self.model_path = model_path
        self.camera_index = camera_index
        self.confidence = confidence
        self.exercise_name = exercise_name
        self.mirror = mirror
        self.show_skeleton = show_skeleton
        self.show_labels = show_labels
        self.result_queue = result_queue

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认不暂停

        self.model: Optional[YOLO] = None
        self.capture: Optional[cv2.VideoCapture] = None
        self.analyzer: Optional[PoseAnalyzer] = None
        self.engine: Optional[ContextEngine] = None
        self.heatmap: Optional[JointAngleHeatmap] = None
        self.fps_ema: float = 0.0
        self.last_frame_time: float = 0.0

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()  # 解除暂停以退出

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def switch_exercise(self, exercise_name: str):
        self.exercise_name = exercise_name
        self.analyzer = PoseAnalyzer(exercise_name) if exercise_name in EXERCISE_STANDARDS else None
        self.engine = ContextEngine(exercise_name)
        self.heatmap = JointAngleHeatmap(exercise_name)

    def run(self):
        try:
            self.model = YOLO(self.model_path)
            self.capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.capture.isOpened():
                self.capture = cv2.VideoCapture(self.camera_index)
            if not self.capture.isOpened():
                self.result_queue.put(("error", "摄像头打开失败"))
                return

            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

            self.analyzer = PoseAnalyzer(self.exercise_name) if self.exercise_name in EXERCISE_STANDARDS else None
            self.engine = ContextEngine(self.exercise_name)
            self.heatmap = JointAngleHeatmap(self.exercise_name)
        except Exception as e:
            self.result_queue.put(("error", f"初始化失败: {e}"))
            return

        while not self._stop_event.is_set():
            if not self._pause_event.is_set():
                time.sleep(0.05)
                continue

            ok, frame = self.capture.read()
            if not ok:
                self.result_queue.put(("error", "读取摄像头失败"))
                break

            if self.mirror:
                frame = cv2.flip(frame, 1)

            annotated, result = self._process_frame(frame)
            self.result_queue.put(("frame", result))

        if self.capture:
            self.capture.release()

    def _process_frame(self, frame) -> tuple:
        t0 = time.time()
        result = DetectionResult(frame=frame)

        results = self.model(frame, conf=self.confidence, verbose=False)
        if not results or not results[0].keypoints or results[0].keypoints.xy is None:
            result.keypoints_detected = False
            result.fps = self._update_fps(t0)
            return frame, result

        kp, conf = self._select_person(results[0])
        if kp is None:
            result.keypoints_detected = False
            result.fps = self._update_fps(t0)
            return frame, result

        result.keypoints_detected = True

        if self.analyzer is not None:
            analysis = self.analyzer.analyze_frame(kp, conf)
            guidance = self.engine.process(analysis) if self.engine else None
            self.heatmap.record_frame(analysis.angles)
            result.analysis = analysis
            result.guidance = guidance

        annotated = frame.copy()
        if self.show_skeleton:
            self._draw_skeleton(annotated, kp, conf)
        self._draw_keypoints(annotated, kp, conf)
        score_total = result.analysis.score.total if result.analysis else 0
        count_val = result.analysis.count if result.analysis else 0
        phase_val = result.analysis.phase if result.analysis else "等待"
        self._draw_overlay(annotated, count_val, phase_val, score_total)
        result.frame = annotated
        result.fps = self._update_fps(t0)
        return annotated, result

    def _update_fps(self, t0):
        now = time.time()
        elapsed = max(now - self.last_frame_time, 1e-6)
        instant_fps = 1.0 / elapsed if elapsed > 0 else 0
        self.fps_ema = 0.85 * self.fps_ema + 0.15 * instant_fps if self.fps_ema else instant_fps
        self.last_frame_time = now
        return self.fps_ema

    def _select_person(self, result):
        if result.keypoints is None or result.keypoints.xy is None:
            return None, None
        xy = result.keypoints.xy.cpu().numpy()
        if len(xy) == 0:
            return None, None
        conf = result.keypoints.conf.cpu().numpy() if result.keypoints.conf is not None else None
        best_idx, best_area = 0, -1
        boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None and len(result.boxes) else None
        for i, pts in enumerate(xy):
            if boxes is not None and i < len(boxes):
                x1, y1, x2, y2 = boxes[i]
                area = max(0, x2 - x1) * max(0, y2 - y1)
            else:
                visible = pts[np.any(pts > 0, axis=1)]
                area = np.prod(visible.max(axis=0) - visible.min(axis=0)) if len(visible) else 0
            if area > best_area:
                best_idx, best_area = i, area
        return xy[best_idx], conf[best_idx] if conf is not None else None

    def _draw_skeleton(self, frame, kp, conf):
        for a, b in SKELETON:
            if valid_point(kp, conf, a) and valid_point(kp, conf, b):
                pa = tuple(np.round(kp[a]).astype(int))
                pb = tuple(np.round(kp[b]).astype(int))
                cv2.line(frame, pa, pb, (20, 184, 166), 3, cv2.LINE_AA)

    def _draw_keypoints(self, frame, kp, conf):
        for i, pt in enumerate(kp):
            if not valid_point(kp, conf, i):
                continue
            x, y = np.round(pt).astype(int)
            cv2.circle(frame, (x, y), 5, (250, 204, 21), -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), 7, (17, 24, 39), 2, cv2.LINE_AA)
            if self.show_labels:
                label = f"{i}:{KEYPOINT_NAMES[i]}"
                cv2.putText(frame, label, (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.42, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, label, (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.42, (17, 24, 39), 1, cv2.LINE_AA)

    def _draw_overlay(self, frame, count: int, phase: str, score: float):
        exercise_en = EXERCISE_ENGLISH_NAMES.get(self.exercise_name, self.exercise_name)
        phase_en = PHASE_ENGLISH_NAMES.get(phase, phase)

        lines = [
            f"Action: {exercise_en}",
            f"Count: {count}",
            f"Phase: {phase_en}",
        ]
        if score > 0:
            lines.append(f"Score: {score:.0f}/100")
        lines.append(f"FPS: {self.fps_ema:.1f}")

        x, y = 18, 28
        box_h = 34 * len(lines) + 18
        cv2.rectangle(frame, (10, 10), (320, box_h), (15, 23, 42), -1)
        cv2.rectangle(frame, (10, 10), (320, box_h), (20, 184, 166), 2)
        for line in lines:
            cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)
            y += 34


# ============================================================================
# 训练历史管理
# ============================================================================

@dataclass
class SessionRecord:
    """单次训练会话记录."""
    session_id: str = ""
    exercise: str = ""
    start_time: str = ""
    duration_seconds: float = 0.0
    total_reps: int = 0
    best_score: float = 0.0
    avg_score: float = 0.0
    scores: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "exercise": self.exercise,
            "start_time": self.start_time,
            "duration_seconds": round(self.duration_seconds, 1),
            "total_reps": self.total_reps,
            "best_score": round(self.best_score, 1),
            "avg_score": round(self.avg_score, 1),
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionRecord":
        defaults = {
            "session_id": "", "exercise": "", "start_time": "",
            "duration_seconds": 0.0, "total_reps": 0, "best_score": 0.0,
            "avg_score": 0.0, "scores": [], "errors": {},
        }
        return cls(**{k: d.get(k, defaults.get(k)) for k in defaults})


class HistoryManager:
    """训练历史持久化管理."""

    def __init__(self, history_dir: Path = HISTORY_DIR):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save(self, record: SessionRecord):
        path = self.history_dir / f"{record.session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)

    def load_all(self) -> list[SessionRecord]:
        records = []
        for path in sorted(self.history_dir.glob("*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records.append(SessionRecord.from_dict(data))
            except Exception:
                pass
        return records

    def load_recent(self, n: int = 20) -> list[SessionRecord]:
        return self.load_all()[:n]


# ============================================================================
# 主应用
# ============================================================================

class WorkoutApp:
    """YOLO26 居家健身实时交互监控系统 — 统一Tkinter GUI."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("YOLO26 居家健身实时交互监控系统")
        self.root.geometry("1280x900")
        self.root.minsize(1024, 720)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # 状态变量
        self.app_state = "idle"  # idle | running | paused | stopped
        self.model_path = tk.StringVar(value=str(DEFAULT_MODEL_PATH))
        self.camera_index = tk.IntVar(value=0)
        self.exercise_name = tk.StringVar(value="深蹲")
        self.confidence = tk.DoubleVar(value=0.35)
        self.show_skeleton = tk.BooleanVar(value=True)
        self.show_labels = tk.BooleanVar(value=True)
        self.mirror_camera = tk.BooleanVar(value=True)

        # 显示变量
        self.status_text = tk.StringVar(value="就绪：选择动作后点击 ▶ 开始训练")
        self.count_text = tk.StringVar(value="0")
        self.phase_text = tk.StringVar(value="等待")
        self.metric_text = tk.StringVar(value="-")
        self.fps_text = tk.StringVar(value="0.0")
        self.score_text = tk.StringVar(value="--")
        self.angle_score_text = tk.StringVar(value="--")
        self.temporal_score_text = tk.StringVar(value="--")
        self.symmetry_score_text = tk.StringVar(value="--")
        self.hold_time_text = tk.StringVar(value="0.0s")
        self.errors_text = tk.StringVar(value="")
        self.guidance_text = tk.StringVar(value="")

        # 检测组件
        self.detection_thread: Optional[DetectionThread] = None
        self.result_queue: queue.Queue = queue.Queue(maxsize=2)

        # 历史管理
        self.history_mgr = HistoryManager()
        self.session_record: Optional[SessionRecord] = None
        self.session_start: float = 0.0
        self._session_scores: list = []

        # 聊天
        self.chat_initialized = False
        self.chat_processing = False
        self.chat_model_size = tk.StringVar(value=CHAT_DEFAULT_MODEL_SIZE)
        self.chat_lora_path = tk.StringVar(value="")
        # 远程 API 模式
        self.chat_use_remote = tk.BooleanVar(value=False)
        self.chat_api_key = tk.StringVar(value="")
        self.chat_model_code = tk.StringVar(value="")
        self._load_api_config()

        # 实时 LLM 教练
        self.coach = RealTimeCoach()
        self._latest_analysis: Optional[AnalysisResult] = None

        # 构建UI
        self._setup_style()
        self._build_ui()
        self._poll_queue()
        self._init_chat()

        self.root.after(200, lambda: self.chat_input.focus_set())

    # ---- 样式 ----

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f6f7f9", font=("Microsoft YaHei UI", 10))
        style.configure("Panel.TLabel", background="#ffffff", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"), background="#ffffff")
        style.configure("Count.TLabel", font=("Microsoft YaHei UI", 42, "bold"), background="#ffffff", foreground="#0f766e")
        style.configure("Score.TLabel", font=("Microsoft YaHei UI", 28, "bold"), foreground="#0f766e", background="#ffffff")
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Start.TButton", font=("Microsoft YaHei UI", 12, "bold"), foreground="#ffffff")
        style.configure("Warning.TLabel", foreground="#dc2626")
        style.configure("Good.TLabel", foreground="#16a34a")

    # ---- UI搭建 ----

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # 上半部分：视频 + 控制面板
        top = ttk.Frame(main)
        top.pack(fill=tk.BOTH, expand=True)

        # 视频区域
        video_frame = ttk.Frame(top)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.video_label = tk.Label(video_frame, text="摄像头未启动", bg="#111827",
                                     fg="#e5e7eb", font=("Microsoft YaHei UI", 18), anchor="center")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        self.status_bar = ttk.Label(video_frame, textvariable=self.status_text, anchor="w")
        self.status_bar.pack(fill=tk.X, pady=(6, 0))

        # 控制面板 (右侧)
        self._build_control_panel(top)

        # 分隔线
        ttk.Separator(main).pack(fill=tk.X, pady=(6, 0))

        # 底部：聊天面板
        self._build_chat_panel(main)

    def _build_control_panel(self, parent):
        cp = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        cp.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        cp.configure(width=340)
        cp.pack_propagate(False)

        ttk.Label(cp, text="YOLO26 健身教练", style="Title.TLabel").pack(anchor="w")
        ttk.Label(cp, text="实时姿态检测 · 动作评分 · AI指导", style="Panel.TLabel").pack(anchor="w", pady=(2, 14))

        # 核心指标卡片
        grid = ttk.Frame(cp, style="Panel.TFrame")
        grid.pack(fill=tk.X)
        self._card(grid, "次数", self.count_text, "Count.TLabel", 0, 0)
        self._card(grid, "阶段", self.phase_text, "Panel.TLabel", 0, 1)
        self._card(grid, "角度/状态", self.metric_text, "Panel.TLabel", 1, 0)
        self._card(grid, "FPS", self.fps_text, "Panel.TLabel", 1, 1)

        ttk.Separator(cp).pack(fill=tk.X, pady=10)

        # 评分区域
        ttk.Label(cp, text="动作评分 (0-100)", style="Panel.TLabel",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        score_row = ttk.Frame(cp, style="Panel.TFrame")
        score_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(score_row, textvariable=self.score_text, style="Score.TLabel").pack(side=tk.LEFT)
        ttk.Label(score_row, text=" 分", style="Panel.TLabel", font=("Microsoft YaHei UI", 12)).pack(side=tk.LEFT)

        sg = ttk.Frame(cp, style="Panel.TFrame")
        sg.pack(fill=tk.X, pady=(4, 0))
        self._card(sg, "关节角度", self.angle_score_text, "Panel.TLabel", 0, 0)
        self._card(sg, "时序", self.temporal_score_text, "Panel.TLabel", 0, 1)
        self._card(sg, "对称性", self.symmetry_score_text, "Panel.TLabel", 1, 0)
        self._card(sg, "保持时间", self.hold_time_text, "Panel.TLabel", 1, 1)

        ttk.Separator(cp).pack(fill=tk.X, pady=10)

        # 错误提示
        ttk.Label(cp, text="动作纠错", style="Panel.TLabel",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        self.errors_label = ttk.Label(cp, textvariable=self.errors_text,
                                       style="Panel.TLabel", wraplength=300,
                                       foreground="#dc2626", justify=tk.LEFT)
        self.errors_label.pack(fill=tk.X, pady=(4, 0))

        # 教练指导
        self.guidance_label = ttk.Label(cp, textvariable=self.guidance_text,
                                         style="Panel.TLabel", wraplength=300,
                                         foreground="#0f766e", justify=tk.LEFT,
                                         font=("Microsoft YaHei UI", 10, "italic"))
        self.guidance_label.pack(fill=tk.X, pady=(4, 0))

        ttk.Separator(cp).pack(fill=tk.X, pady=10)

        # 动作选择
        ttk.Label(cp, text="动作类型", style="Panel.TLabel").pack(anchor="w")
        cb = ttk.Combobox(cp, textvariable=self.exercise_name,
                          values=ALL_EXERCISES, state="readonly")
        cb.pack(fill=tk.X, pady=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_exercise_change())

        # 设置折叠区
        self._build_settings(cp)

        ttk.Separator(cp).pack(fill=tk.X, pady=10)

        # 控制按钮
        btn_frame = ttk.Frame(cp, style="Panel.TFrame")
        btn_frame.pack(fill=tk.X)

        self.start_btn = tk.Button(btn_frame, text="▶ 开始训练", font=("Microsoft YaHei UI", 12, "bold"),
                                    bg="#0f766e", fg="white", activebackground="#0d6b63",
                                    activeforeground="white", relief=tk.FLAT, padx=16, pady=8,
                                    command=self.start)
        self.start_btn.pack(fill=tk.X, pady=(0, 6))

        self.pause_btn = tk.Button(btn_frame, text="⏸ 暂停", font=("Microsoft YaHei UI", 11, "bold"),
                                    bg="#d97706", fg="white", activebackground="#b45309",
                                    activeforeground="white", relief=tk.FLAT, padx=14, pady=6,
                                    command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(fill=tk.X, pady=(0, 6))

        self.stop_btn = tk.Button(btn_frame, text="⏹ 停止", font=("Microsoft YaHei UI", 11, "bold"),
                                   bg="#dc2626", fg="white", activebackground="#b91c1c",
                                   activeforeground="white", relief=tk.FLAT, padx=14, pady=6,
                                   command=self.stop, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=(0, 6))

        history_btn = tk.Button(btn_frame, text="📊 训练历史", font=("Microsoft YaHei UI", 10),
                                 bg="#6b7280", fg="white", activebackground="#4b5563",
                                 activeforeground="white", relief=tk.FLAT, padx=12, pady=5,
                                 command=self._show_history)
        history_btn.pack(fill=tk.X)

    def _build_settings(self, parent):
        self.settings_visible = tk.BooleanVar(value=False)

        toggle_btn = ttk.Button(parent, text="⚙ 设置 ▼", command=self._toggle_settings)
        toggle_btn.pack(fill=tk.X, pady=(0, 4))

        self.settings_frame = ttk.Frame(parent, style="Panel.TFrame")
        self.settings_frame.pack(fill=tk.X)
        self.settings_frame.pack_forget()

        ttk.Label(self.settings_frame, text="模型路径", style="Panel.TLabel").pack(anchor="w")
        mr = ttk.Frame(self.settings_frame, style="Panel.TFrame")
        mr.pack(fill=tk.X, pady=(2, 6))
        ttk.Entry(mr, textvariable=self.model_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(mr, text="浏览", command=self._browse_model).pack(side=tk.RIGHT, padx=(4, 0))

        ttk.Label(self.settings_frame, text="摄像头编号", style="Panel.TLabel").pack(anchor="w")
        ttk.Spinbox(self.settings_frame, from_=0, to=8, textvariable=self.camera_index, width=8).pack(fill=tk.X, pady=(2, 6))

        ttk.Label(self.settings_frame, text="检测置信度", style="Panel.TLabel").pack(anchor="w")
        cr = ttk.Frame(self.settings_frame, style="Panel.TFrame")
        cr.pack(fill=tk.X, pady=(2, 6))
        ttk.Scale(cr, from_=0.1, to=0.8, variable=self.confidence).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(cr, textvariable=self.confidence, style="Panel.TLabel", width=5).pack(side=tk.RIGHT, padx=(4, 0))

        ttk.Label(self.settings_frame, text="聊天模型大小", style="Panel.TLabel").pack(anchor="w")
        ttk.Combobox(self.settings_frame, textvariable=self.chat_model_size,
                     values=CHAT_MODEL_SIZES, state="readonly", width=10).pack(fill=tk.X, pady=(2, 6))

        ttk.Label(self.settings_frame, text="LoRA适配器路径 (可选)", style="Panel.TLabel").pack(anchor="w")
        lora_row = ttk.Frame(self.settings_frame, style="Panel.TFrame")
        lora_row.pack(fill=tk.X, pady=(2, 6))
        ttk.Entry(lora_row, textvariable=self.chat_lora_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(lora_row, text="浏览", command=self._browse_lora).pack(side=tk.RIGHT, padx=(4, 0))

        ttk.Separator(self.settings_frame).pack(fill=tk.X, pady=6)
        ttk.Checkbutton(self.settings_frame, text="启用远程 API 模式 (百炼API推理)",
                        variable=self.chat_use_remote,
                        command=self._toggle_remote_mode).pack(anchor="w", pady=(4, 2))

        self.remote_frame = ttk.Frame(self.settings_frame, style="Panel.TFrame")
        ttk.Label(self.remote_frame, text="API Key", style="Panel.TLabel").pack(anchor="w")
        ttk.Entry(self.remote_frame, textvariable=self.chat_api_key, show="*").pack(fill=tk.X, pady=(2, 4))
        ttk.Label(self.remote_frame, text="模型 Code", style="Panel.TLabel").pack(anchor="w")
        ttk.Entry(self.remote_frame, textvariable=self.chat_model_code).pack(fill=tk.X, pady=(2, 4))
        if not self.chat_use_remote.get():
            self.remote_frame.pack_forget()
        else:
            self.remote_frame.pack(fill=tk.X)

        ttk.Checkbutton(self.settings_frame, text="显示骨架连线", variable=self.show_skeleton).pack(anchor="w")
        ttk.Checkbutton(self.settings_frame, text="显示关键点编号", variable=self.show_labels).pack(anchor="w")
        ttk.Checkbutton(self.settings_frame, text="镜像摄像头画面", variable=self.mirror_camera).pack(anchor="w")

    def _build_chat_panel(self, parent):
        chat_frame = tk.Frame(parent, bg="#ffffff", highlightbackground="#d1d5db", highlightthickness=1)
        chat_frame.pack(fill=tk.BOTH, expand=False, pady=(6, 0))

        header = tk.Frame(chat_frame, bg="#ffffff")
        header.pack(fill=tk.X, padx=10, pady=(8, 2))
        tk.Label(header, text="🤖 AI 健身助手 (Qwen2.5 BaseModel)",
                 font=("Microsoft YaHei UI", 13, "bold"), bg="#ffffff", fg="#111827").pack(side=tk.LEFT)
        self.chat_status_label = tk.Label(header, text="", font=("Microsoft YaHei UI", 9),
                                           bg="#ffffff", fg="#6b7280")
        self.chat_status_label.pack(side=tk.RIGHT)

        display_frame = tk.Frame(chat_frame, bg="#ffffff")
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 0))

        self.chat_display = tk.Text(display_frame, font=("Microsoft YaHei UI", 10),
                                     bg="#f3f4f6", fg="#111827", wrap=tk.WORD,
                                     height=4, padx=6, pady=4, relief=tk.FLAT, borderwidth=0,
                                     state=tk.DISABLED)
        chat_scroll = tk.Scrollbar(display_frame, orient=tk.VERTICAL, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=chat_scroll.set)
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_display.tag_configure("user", foreground="#0f766e", font=("Microsoft YaHei UI", 10, "bold"),
                                         lmargin1=40, lmargin2=40, spacing3=6)
        self.chat_display.tag_configure("assistant", foreground="#111827", font=("Microsoft YaHei UI", 10),
                                         lmargin1=10, lmargin2=10, spacing3=6)
        self.chat_display.tag_configure("system_msg", foreground="#6b7280",
                                         font=("Microsoft YaHei UI", 9, "italic"),
                                         lmargin1=10, lmargin2=10, spacing3=4)

        input_row = tk.Frame(chat_frame, bg="#ffffff")
        input_row.pack(fill=tk.X, padx=10, pady=(4, 10))

        self.chat_input = tk.Text(input_row, font=("Microsoft YaHei UI", 10),
                                   bg="white", fg="black", insertbackground="black",
                                   relief=tk.SOLID, borderwidth=2, height=2,
                                   padx=8, pady=4, wrap=tk.WORD)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind("<Return>", self._on_chat_enter)
        self.chat_input.bind("<KeyRelease>", self._on_input_change)

        self.send_btn = tk.Button(input_row, text="发送", font=("Microsoft YaHei UI", 10, "bold"),
                                   bg="#0f766e", fg="white", activebackground="#0d6b63",
                                   activeforeground="white", relief=tk.FLAT, padx=16, pady=4,
                                   command=self._send_chat)
        self.send_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.send_btn.configure(state=tk.DISABLED)

        self._append_chat("system_msg", CHAT_WELCOME)

    def _card(self, parent, title, var, style, row, col):
        card = ttk.Frame(parent, style="Panel.TFrame", padding=6)
        card.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
        parent.columnconfigure(col, weight=1)
        ttk.Label(card, text=title, style="Panel.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=var, style=style).pack(anchor="w")

    def _toggle_settings(self):
        if self.settings_visible.get():
            self.settings_frame.pack_forget()
            self.settings_visible.set(False)
        else:
            self.settings_frame.pack(fill=tk.X)
            self.settings_visible.set(True)

    def _browse_model(self):
        path = filedialog.askopenfilename(
            title="选择 YOLO pose 模型",
            filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")],
        )
        if path:
            self.model_path.set(path)

    def _browse_lora(self):
        path = filedialog.askdirectory(title="选择 LoRA adapter 目录")
        if path:
            self.chat_lora_path.set(path)
            # Reset chat to reload with new adapter
            self.chat_initialized = False
            self.chat_status_label.configure(text="适配器已更换，下次启动生效")

    def _toggle_remote_mode(self):
        if self.chat_use_remote.get():
            self.remote_frame.pack(fill=tk.X)
        else:
            self.remote_frame.pack_forget()
        # Reset chat to re-init with new mode
        self.chat_initialized = False
        self._save_api_config()

    def _api_config_path(self):
        return BASE_DIR / "data" / "api_config.json"

    def _load_api_config(self):
        path = self._api_config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.chat_use_remote.set(cfg.get("use_remote", False))
                self.chat_api_key.set(cfg.get("api_key", ""))
                self.chat_model_code.set(cfg.get("model_code", ""))
            except Exception:
                pass

    def _save_api_config(self):
        path = self._api_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        cfg = {
            "use_remote": self.chat_use_remote.get(),
            "api_key": self.chat_api_key.get(),
            "model_code": self.chat_model_code.get(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    def _on_exercise_change(self):
        exercise = self.exercise_name.get()
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.switch_exercise(exercise)
        self._reset_metrics()

    def _reset_metrics(self):
        self.count_text.set("0")
        self.phase_text.set("等待")
        self.metric_text.set("-")
        self.score_text.set("--")
        self.angle_score_text.set("--")
        self.temporal_score_text.set("--")
        self.symmetry_score_text.set("--")
        self.hold_time_text.set("0.0s")
        self.errors_text.set("")
        self.guidance_text.set("")

    # ---- 状态机 ----

    def start(self):
        if self.app_state == "running":
            return

        model_path = Path(self.model_path.get())
        if not model_path.exists():
            messagebox.showerror("模型不存在", f"找不到模型文件：\n{model_path}")
            return

        self._reset_metrics()
        self.coach.reset()
        self._latest_analysis = None
        self.result_queue = queue.Queue(maxsize=2)

        if self.app_state == "paused":
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.resume()
            self.app_state = "running"
            self._update_button_states()
            self.status_text.set("训练中...")
        else:
            self.detection_thread = DetectionThread(
                model_path=str(model_path),
                camera_index=int(self.camera_index.get()),
                confidence=float(self.confidence.get()),
                exercise_name=self.exercise_name.get(),
                mirror=self.mirror_camera.get(),
                show_skeleton=self.show_skeleton.get(),
                show_labels=self.show_labels.get(),
                result_queue=self.result_queue,
            )
            self.detection_thread.start()
            self.app_state = "running"
            self._update_button_states()
            self.status_text.set("正在启动摄像头和模型...")

            # 开始会话记录
            self.session_start = time.time()
            self._session_scores = []
            self.session_record = SessionRecord(
                session_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
                exercise=self.exercise_name.get(),
                start_time=datetime.now().isoformat(),
            )

    def toggle_pause(self):
        if self.app_state == "running":
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.pause()
            self.app_state = "paused"
            self.pause_btn.configure(text="▶ 继续")
            self.status_text.set("已暂停")
        elif self.app_state == "paused":
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.resume()
            self.app_state = "running"
            self.pause_btn.configure(text="⏸ 暂停")
            self.status_text.set("训练中...")
        self._update_button_states()

    def stop(self):
        if self.detection_thread:
            self.detection_thread.stop()
        self.app_state = "stopped"
        self._update_button_states()
        self.status_text.set("已停止")
        self._save_session()

    def close(self):
        if self.detection_thread:
            self.detection_thread.stop()
        self.root.destroy()

    def _update_button_states(self):
        if self.app_state == "idle" or self.app_state == "stopped":
            self.start_btn.configure(text="▶ 开始训练", state=tk.NORMAL)
            self.pause_btn.configure(text="⏸ 暂停", state=tk.DISABLED)
            self.stop_btn.configure(state=tk.DISABLED)
        elif self.app_state == "running":
            self.start_btn.configure(state=tk.DISABLED)
            self.pause_btn.configure(text="⏸ 暂停", state=tk.NORMAL)
            self.stop_btn.configure(state=tk.NORMAL)
        elif self.app_state == "paused":
            self.start_btn.configure(state=tk.DISABLED)
            self.pause_btn.configure(text="▶ 继续", state=tk.NORMAL)
            self.stop_btn.configure(state=tk.NORMAL)

    def _save_session(self):
        if self.session_record is None:
            return
        self.session_record.duration_seconds = time.time() - self.session_start
        self.session_record.exercise = self.exercise_name.get()

        if self._session_scores:
            self.session_record.avg_score = float(np.mean(self._session_scores))
            self.session_record.best_score = float(np.max(self._session_scores))

        if self.detection_thread and self.detection_thread.analyzer:
            self.session_record.total_reps = self.detection_thread.analyzer.count
            errors = getattr(self.detection_thread.analyzer._error_detector, '_error_counter', {})
            self.session_record.errors = dict(errors)

        self.history_mgr.save(self.session_record)
        self.status_text.set(f"训练已保存: {self.session_record.session_id}")

    # ---- 主循环 (从检测队列取结果) ----

    def _poll_queue(self):
        """定期轮询检测队列, 在主线程更新UI."""
        try:
            while True:
                msg_type, payload = self.result_queue.get_nowait()
                if msg_type == "error":
                    self.status_text.set(payload)
                    self.stop()
                elif msg_type == "frame":
                    self._update_frame(payload)
        except queue.Empty:
            pass

        if self.app_state == "running":
            self.root.after(10, self._poll_queue)
        else:
            self.root.after(50, self._poll_queue)

    def _update_frame(self, result: DetectionResult):
        # 渲染画面
        rgb = cv2.cvtColor(result.frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        label_w = max(self.video_label.winfo_width(), 640)
        label_h = max(self.video_label.winfo_height(), 360)
        image.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(image=image)
        self.video_label.configure(image=self._photo, text="")

        # FPS
        self.fps_text.set(f"{result.fps:.1f}")

        if not result.keypoints_detected:
            self.status_text.set("未检测到人体 — 请确保全身在画面内")
            self.score_text.set("--")
            self.angle_score_text.set("--")
            self.temporal_score_text.set("--")
            self.symmetry_score_text.set("--")
            self.errors_text.set("")
            self.guidance_text.set("")
            return

        self.status_text.set("检测中 · 姿态分析运行中")

        analysis = result.analysis
        if analysis is None:
            return

        # 计数 / 阶段
        self.count_text.set(str(analysis.count))
        self.phase_text.set(analysis.phase)
        exercise = self.exercise_name.get()
        metric = analysis.angles.primary_angle(exercise)
        self.metric_text.set(self._fmt_metric(metric))

        # 评分
        s = analysis.score
        self.score_text.set(f"{s.total:.0f}")
        self.angle_score_text.set(f"{s.angle_score:.0f}/40")
        self.temporal_score_text.set(f"{s.temporal_score:.0f}/30")
        self.symmetry_score_text.set(f"{s.symmetry_score:.0f}/30")
        self.hold_time_text.set(f"{analysis.hold_time:.1f}s")

        if self._session_scores is not None and s.total > 0:
            self._session_scores.append(s.total)

        # 错误
        if analysis.errors:
            err_lines = [f"⚠ {e.name}: {e.suggestion}" for e in analysis.errors]
            self.errors_text.set("\n".join(err_lines))
            self.errors_label.configure(foreground="#dc2626")
        else:
            self.errors_text.set("✓ 动作标准，无检测错误")
            self.errors_label.configure(foreground="#16a34a")

        # 教练指导
        if result.guidance:
            self.guidance_text.set(f"💬 {result.guidance.text}")
        else:
            self.guidance_text.set("")

        # 存储最新分析结果供聊天上下文使用
        self._latest_analysis = analysis

        # 实时 LLM 教练主动推送
        if (self.chat_use_remote.get() and self.chat_initialized
                and not self.chat_processing
                and self.detection_thread and self.detection_thread.engine):
            context_str = self.coach.evaluate_frame(
                analysis,
                self.detection_thread.engine.state,
                self.exercise_name.get(),
            )
            if context_str:
                self._proactive_coach_call(context_str)

    def _fmt_metric(self, metric):
        if metric is None:
            return "-"
        if self.exercise_name.get() == "开合跳":
            return "打开" if (metric or 0) > 0.5 else "闭合"
        return f"{metric:.0f}°"

    # ---- 训练历史 ----

    def _show_history(self):
        records = self.history_mgr.load_recent(30)

        win = tk.Toplevel(self.root)
        win.title("训练历史记录")
        win.geometry("700x500")
        win.minsize(500, 350)

        if not records:
            ttk.Label(win, text="暂无训练记录\n\n开始一次训练后会自动保存",
                      font=("Microsoft YaHei UI", 12), foreground="#6b7280").pack(expand=True)
            return

        # Treeview
        cols = ("时间", "动作", "时长", "次数", "最佳分", "平均分")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor="center")

        tree.column("时间", width=150)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for r in records:
            tree.insert("", tk.END, values=(
                r.start_time[:19] if r.start_time else r.session_id,
                r.exercise,
                f"{r.duration_seconds:.0f}s",
                r.total_reps,
                f"{r.best_score:.0f}" if r.best_score > 0 else "-",
                f"{r.avg_score:.0f}" if r.avg_score > 0 else "-",
            ))

        scrollbar = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(10, 10))

    # ---- 聊天助手 ----

    def _init_chat(self):
        # 有远程 API 凭证时优先使用远程模式
        has_remote_creds = bool(self.chat_api_key.get() and self.chat_model_code.get())
        if has_remote_creds:
            if not self.chat_use_remote.get():
                self.chat_use_remote.set(True)
                self._save_api_config()
            self.chat_initialized = True
            self.chat_status_label.configure(text="7B 远程 API 就绪")
            return
        if not _BASE_MODEL_AVAILABLE:
            self._append_chat("system_msg",
                "⚠ 模型系统不可用。运行: pip install torch transformers\n"
                "或启用「远程 API 模式」使用百炼云端推理。")
            self.chat_status_label.configure(text="未安装依赖")
            return
        threading.Thread(target=self._load_chat_model, daemon=True).start()

    def _load_chat_model(self):
        try:
            model_size = self.chat_model_size.get()
            lora_path = self.chat_lora_path.get() or None
            self.root.after(0, lambda: self.chat_status_label.configure(
                text=f"加载 {model_size} 模型中…"))
            BaseModel.get_instance(model_size=model_size, lora_path=lora_path)
            self.chat_initialized = True
            device = "GPU" if __import__('torch').cuda.is_available() else "CPU"
            label = f"{model_size} ({device})"
            if lora_path:
                label += " +LoRA"
            self.root.after(0, lambda: self.chat_status_label.configure(text=label))
        except Exception as e:
            self.root.after(0, lambda: self._append_chat("system_msg",
                f"模型加载失败: {e}\n请检查网络连接或设置 HuggingFace 镜像: HF_ENDPOINT=https://hf-mirror.com"))
            self.root.after(0, lambda: self.chat_status_label.configure(text="加载失败"))

    def _append_chat(self, role, text):
        self.chat_display.configure(state=tk.NORMAL)
        if role == "user":
            self.chat_display.insert(tk.END, f"🧑 你\n{text}\n\n", "user")
        elif role == "assistant":
            self.chat_display.insert(tk.END, f"🤖 助手\n{text}\n\n", "assistant")
        else:
            self.chat_display.insert(tk.END, f"{text}\n\n", "system_msg")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _on_input_change(self, event=None):
        if self.chat_processing:
            return
        text = self.chat_input.get("1.0", "end-1c").strip()
        self.send_btn.configure(state=tk.NORMAL if text else tk.DISABLED)

    def _on_chat_enter(self, event):
        if event.state & 0x1:
            return None
        self._send_chat()
        return "break"

    def _send_chat(self):
        if self.chat_processing:
            return
        if not self.chat_initialized:
            self._append_chat("system_msg", "⚠ AI助手未就绪，请确认本地 Qwen2.5 模型已正确加载。")
            self.chat_input.delete("1.0", tk.END)
            return

        user_text = self.chat_input.get("1.0", "end-1c").strip()
        if not user_text:
            return

        self.chat_input.delete("1.0", tk.END)
        self.chat_input.configure(state=tk.DISABLED)
        self.send_btn.configure(state=tk.DISABLED, text="思考中…")
        self.chat_processing = True
        self.chat_status_label.configure(text="回复中…")
        self._append_chat("user", user_text)

        # Build real-time context if training is active
        context = None
        if self.app_state == "running" and self.detection_thread and self.detection_thread.engine:
            context = self.coach.build_chat_context(
                self._latest_analysis,
                self.detection_thread.engine.state,
                self.exercise_name.get(),
                user_text,
            )

        threading.Thread(target=self._generate_chat, args=(user_text, context), daemon=True).start()

    def _generate_chat(self, user_message, context=None):
        try:
            # Choose system prompt and message content based on context
            if context:
                system_prompt = COACH_SYSTEM_PROMPT
                user_content = context
            else:
                system_prompt = CHAT_SYSTEM_PROMPT
                user_content = user_message

            if self.chat_use_remote.get() and self.chat_api_key.get():
                from openai import OpenAI
                client = OpenAI(
                    api_key=self.chat_api_key.get(),
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                )
                completion = client.chat.completions.create(
                    model=self.chat_model_code.get(),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.7,
                    max_tokens=800,
                )
                reply = completion.choices[0].message.content
            else:
                model = BaseModel.get_instance(model_size=self.chat_model_size.get())
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ]
                reply = model.chat(messages, max_tokens=800, temperature=0.7)
        except Exception as e:
            reply = f"请求失败：{e}"
        self.root.after(0, self._on_chat_response, reply)

    def _on_chat_response(self, reply):
        self._append_chat("assistant", reply)
        self.chat_input.configure(state=tk.NORMAL)
        self.chat_input.focus_set()
        self.send_btn.configure(text="发送")
        self._on_input_change()
        self.chat_processing = False
        if self.chat_use_remote.get():
            self.chat_status_label.configure(text="7B 远程 API 就绪")
        else:
            torch_available = False
            try:
                import torch; torch_available = torch.cuda.is_available()
            except Exception:
                pass
            device = "GPU" if torch_available else "CPU"
            self.chat_status_label.configure(text=f"{self.chat_model_size.get()} ({device})")

    # ---- 实时 LLM 教练主动推送 ----

    def _proactive_coach_call(self, context_str: str):
        """Fire a proactive coaching API call (auto-push to chat)."""
        self.chat_processing = True
        self.chat_status_label.configure(text="教练思考中…")
        threading.Thread(
            target=self._generate_coach_message,
            args=(context_str,),
            daemon=True,
        ).start()

    def _generate_coach_message(self, context_str: str):
        """Generate a proactive coaching message (no user input)."""
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.chat_api_key.get(),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            completion = client.chat.completions.create(
                model=self.chat_model_code.get(),
                messages=[
                    {"role": "system", "content": COACH_SYSTEM_PROMPT_PROACTIVE},
                    {"role": "user", "content": context_str},
                ],
                temperature=0.7,
                max_tokens=300,
            )
            reply = completion.choices[0].message.content
        except Exception:
            reply = None
        self.root.after(0, self._on_coach_response, reply)

    def _on_coach_response(self, reply):
        """Handle proactive coaching response."""
        if reply:
            self._append_chat("assistant", reply)
        self.chat_processing = False
        if self.chat_use_remote.get():
            self.chat_status_label.configure(text="7B 远程 API 就绪")


# ============================================================================
# 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="YOLO26 居家健身实时交互监控系统")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="YOLO pose 模型路径")
    parser.add_argument("--camera", type=int, default=0, help="摄像头编号")
    parser.add_argument("--exercise", default="深蹲", choices=ALL_EXERCISES, help="初始动作")
    args = parser.parse_args()

    root = tk.Tk()
    app = WorkoutApp(root)
    app.model_path.set(args.model)
    app.camera_index.set(args.camera)
    app.exercise_name.set(args.exercise)
    root.mainloop()


if __name__ == "__main__":
    main()
