import argparse
import math
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent))
from code.pose_analyzer import PoseAnalyzer, EXERCISE_STANDARDS


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = BASE_DIR / "yolo26n-pose.pt"

KEYPOINT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

EXERCISE_ENGLISH_NAMES = {
    "深蹲": "squat",
    "俯卧撑": "push-up",
    "仰卧起坐": "sit-up",
    "弓步": "lunge",
    "哑铃弯举": "biceps curl",
    "开合跳": "jumping jack",
    "引体向上": "pull-up",
    "臀桥": "glute bridge",
    "高抬腿": "high knees",
    "肩推": "shoulder press",
    "侧平举": "lateral raise",
}

PHASE_ENGLISH_NAMES = {
    "等待": "waiting",
    "低位": "low",
    "高位": "high",
}

SKELETON = [
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 6),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
]

SIDE_KEYPOINTS = {
    "左侧": {
        "elbow": (5, 7, 9),
        "knee": (11, 13, 15),
        "hip": (5, 11, 13),
        "shoulder": (7, 5, 11),
    },
    "右侧": {
        "elbow": (6, 8, 10),
        "knee": (12, 14, 16),
        "hip": (6, 12, 14),
        "shoulder": (8, 6, 12),
    },
}


@dataclass(frozen=True)
class ExerciseConfig:
    label: str
    metric: str
    low_threshold: float
    high_threshold: float
    count_on: str
    unit: str = "deg"
    hint: str = ""


EXERCISES = {
    "深蹲": ExerciseConfig(
        label="深蹲",
        metric="knee_angle",
        low_threshold=105,
        high_threshold=160,
        count_on="high",
        hint="下蹲后站直计 1 次",
    ),
    "俯卧撑": ExerciseConfig(
        label="俯卧撑",
        metric="elbow_angle",
        low_threshold=95,
        high_threshold=155,
        count_on="high",
        hint="屈肘后撑起计 1 次",
    ),
    "仰卧起坐": ExerciseConfig(
        label="仰卧起坐",
        metric="hip_angle",
        low_threshold=85,
        high_threshold=135,
        count_on="low",
        hint="躯干抬起计 1 次",
    ),
    "弓步": ExerciseConfig(
        label="弓步",
        metric="lunge_angle",
        low_threshold=100,
        high_threshold=155,
        count_on="high",
        hint="下压后回到站姿计 1 次",
    ),
    "哑铃弯举": ExerciseConfig(
        label="哑铃弯举",
        metric="elbow_angle",
        low_threshold=65,
        high_threshold=150,
        count_on="low",
        hint="手臂弯起计 1 次",
    ),
    "开合跳": ExerciseConfig(
        label="开合跳",
        metric="jumping_jack",
        low_threshold=0.2,
        high_threshold=0.8,
        count_on="high",
        unit="state",
        hint="手脚打开计 1 次",
    ),
    "引体向上": ExerciseConfig(
        label="引体向上",
        metric="elbow_angle",
        low_threshold=160,
        high_threshold=60,
        count_on="low",
        hint="下巴过杠计 1 次",
    ),
    "臀桥": ExerciseConfig(
        label="臀桥",
        metric="hip_angle",
        low_threshold=100,
        high_threshold=165,
        count_on="high",
        hint="臀部抬起计 1 次",
    ),
    "高抬腿": ExerciseConfig(
        label="高抬腿",
        metric="hip_angle",
        low_threshold=160,
        high_threshold=100,
        count_on="low",
        hint="膝盖抬高计 1 次",
    ),
    "肩推": ExerciseConfig(
        label="肩推",
        metric="elbow_angle",
        low_threshold=75,
        high_threshold=160,
        count_on="high",
        hint="手臂推起计 1 次",
    ),
    "侧平举": ExerciseConfig(
        label="侧平举",
        metric="shoulder_angle",
        low_threshold=15,
        high_threshold=85,
        count_on="high",
        hint="手臂平举至肩高计 1 次",
    ),
}


def calculate_angle(a, b, c):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    c = np.asarray(c, dtype=np.float32)

    radians = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(
        a[1] - b[1], a[0] - b[0]
    )
    angle = abs(radians * 180.0 / math.pi)
    if angle > 180.0:
        angle = 360.0 - angle
    return angle


def valid_point(keypoints, confidences, index, min_conf=0.15):
    if index >= len(keypoints):
        return False
    x, y = keypoints[index]
    if x <= 0 and y <= 0:
        return False
    if confidences is not None and confidences[index] < min_conf:
        return False
    return True


def side_angle(keypoints, confidences, joint_name, side):
    ids = SIDE_KEYPOINTS[side][joint_name]
    if all(valid_point(keypoints, confidences, i) for i in ids):
        return calculate_angle(keypoints[ids[0]], keypoints[ids[1]], keypoints[ids[2]])
    return None


def mean_valid(values):
    valid = [v for v in values if v is not None and not math.isnan(v)]
    if not valid:
        return None
    return float(np.mean(valid))


class ExerciseCounter:
    def __init__(self):
        self.count = 0
        self.phase = "等待"
        self.metric_value = None

    def reset(self):
        self.count = 0
        self.phase = "等待"
        self.metric_value = None

    def update(self, exercise_name, keypoints, confidences, side):
        config = EXERCISES[exercise_name]
        value = self._metric(config.metric, keypoints, confidences, side)
        self.metric_value = value

        if value is None:
            return self.count, self.phase, None

        low = config.low_threshold
        high = config.high_threshold

        if config.count_on == "high":
            if value < low:
                self.phase = "低位"
            elif value > high and self.phase == "低位":
                self.count += 1
                self.phase = "高位"
            elif value > high and self.phase == "等待":
                self.phase = "高位"
        else:
            if value > high:
                self.phase = "高位"
            elif value < low and self.phase == "高位":
                self.count += 1
                self.phase = "低位"
            elif value < low and self.phase == "等待":
                self.phase = "低位"

        return self.count, self.phase, value

    def _metric(self, metric, keypoints, confidences, side):
        if metric == "elbow_angle":
            return self._joint_angle(keypoints, confidences, "elbow", side)
        if metric == "knee_angle":
            return self._joint_angle(keypoints, confidences, "knee", side)
        if metric == "hip_angle":
            return self._joint_angle(keypoints, confidences, "hip", side)
        if metric == "shoulder_angle":
            return self._joint_angle(keypoints, confidences, "shoulder", side)
        if metric == "lunge_angle":
            values = [
                side_angle(keypoints, confidences, "knee", "左侧"),
                side_angle(keypoints, confidences, "knee", "右侧"),
            ]
            if side in SIDE_KEYPOINTS:
                return side_angle(keypoints, confidences, "knee", side)
            valid = [v for v in values if v is not None]
            return min(valid) if valid else None
        if metric == "jumping_jack":
            return self._jumping_jack_score(keypoints, confidences)
        return None

    def _joint_angle(self, keypoints, confidences, joint_name, side):
        if side in SIDE_KEYPOINTS:
            return side_angle(keypoints, confidences, joint_name, side)
        return mean_valid(
            [
                side_angle(keypoints, confidences, joint_name, "左侧"),
                side_angle(keypoints, confidences, joint_name, "右侧"),
            ]
        )

    def _jumping_jack_score(self, keypoints, confidences):
        required = [5, 6, 9, 10, 15, 16]
        if not all(valid_point(keypoints, confidences, i) for i in required):
            return None

        shoulder_width = np.linalg.norm(keypoints[5] - keypoints[6])
        ankle_width = np.linalg.norm(keypoints[15] - keypoints[16])
        if shoulder_width < 1:
            return None

        wrists_up = keypoints[9][1] < keypoints[5][1] and keypoints[10][1] < keypoints[6][1]
        legs_open = ankle_width > shoulder_width * 1.35
        return 1.0 if wrists_up and legs_open else 0.0


class WorkoutMonitoringApp:
    def __init__(self, root):
        self.root = root
        self.root.title("健身动作识别计数系统")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.model = None
        self.capture = None
        self.running = False
        self.last_frame_time = time.time()
        self.fps = 0.0
        self.analyzer = PoseAnalyzer("深蹲")
        self.counter = ExerciseCounter()
        self.photo = None

        self.model_path = tk.StringVar(value=str(DEFAULT_MODEL_PATH))
        self.camera_index = tk.IntVar(value=0)
        self.exercise_name = tk.StringVar(value="深蹲")
        self.side_name = tk.StringVar(value="自动")
        self.confidence = tk.DoubleVar(value=0.35)
        self.show_skeleton = tk.BooleanVar(value=True)
        self.show_labels = tk.BooleanVar(value=True)
        self.mirror_camera = tk.BooleanVar(value=True)
        self.status_text = tk.StringVar(value="就绪：选择动作后点击启动摄像头")
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

        self._setup_style()
        self._build_layout()
        self._on_exercise_change()

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
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"))

    def _build_layout(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        video_panel = ttk.Frame(main)
        video_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.video_label = tk.Label(
            video_panel,
            text="摄像头未启动",
            bg="#111827",
            fg="#e5e7eb",
            font=("Microsoft YaHei UI", 18),
            anchor="center",
        )
        self.video_label.pack(fill=tk.BOTH, expand=True)

        status = ttk.Label(video_panel, textvariable=self.status_text, anchor="w")
        status.pack(fill=tk.X, pady=(8, 0))

        control = ttk.Frame(main, style="Panel.TFrame", padding=16)
        control.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        control.configure(width=330)
        control.pack_propagate(False)

        ttk.Label(control, text="健身计数系统", style="Title.TLabel").pack(anchor="w")
        ttk.Label(control, text="实时姿态检测 / 关键点显示 / 动作计数", style="Panel.TLabel").pack(
            anchor="w", pady=(2, 18)
        )

        metric_grid = ttk.Frame(control, style="Panel.TFrame")
        metric_grid.pack(fill=tk.X)
        self._metric_card(metric_grid, "次数", self.count_text, "Count.TLabel", 0, 0)
        self._metric_card(metric_grid, "阶段", self.phase_text, "Panel.TLabel", 0, 1)
        self._metric_card(metric_grid, "角度/状态", self.metric_text, "Panel.TLabel", 1, 0)
        self._metric_card(metric_grid, "FPS", self.fps_text, "Panel.TLabel", 1, 1)

        ttk.Separator(control).pack(fill=tk.X, pady=10)

        # 评分区域
        ttk.Label(control, text="动作评分 (0-100)", style="Panel.TLabel",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        score_row = ttk.Frame(control, style="Panel.TFrame")
        score_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(score_row, textvariable=self.score_text,
                  font=("Microsoft YaHei UI", 28, "bold"),
                  foreground="#0f766e", background="#ffffff").pack(side=tk.LEFT)
        ttk.Label(score_row, text=" 分", style="Panel.TLabel").pack(side=tk.LEFT)

        score_grid = ttk.Frame(control, style="Panel.TFrame")
        score_grid.pack(fill=tk.X, pady=(4, 0))
        self._metric_card(score_grid, "关节角度", self.angle_score_text, "Panel.TLabel", 0, 0)
        self._metric_card(score_grid, "时序", self.temporal_score_text, "Panel.TLabel", 0, 1)
        self._metric_card(score_grid, "对称性", self.symmetry_score_text, "Panel.TLabel", 1, 0)
        self._metric_card(score_grid, "保持时间", self.hold_time_text, "Panel.TLabel", 1, 1)

        ttk.Separator(control).pack(fill=tk.X, pady=10)

        # 错误提示区域
        ttk.Label(control, text="动作纠错", style="Panel.TLabel",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        self.errors_label = ttk.Label(control, textvariable=self.errors_text,
                                       style="Panel.TLabel", wraplength=290,
                                       foreground="#dc2626", justify=tk.LEFT)
        self.errors_label.pack(fill=tk.X, pady=(4, 0))

        ttk.Separator(control).pack(fill=tk.X, pady=10)

        ttk.Label(control, text="动作类型", style="Panel.TLabel").pack(anchor="w")
        all_exercises = list(dict.fromkeys(list(EXERCISE_STANDARDS.keys()) + list(EXERCISES.keys())))
        exercise_box = ttk.Combobox(
            control,
            textvariable=self.exercise_name,
            values=all_exercises,
            state="readonly",
        )
        exercise_box.pack(fill=tk.X, pady=(4, 10))
        exercise_box.bind("<<ComboboxSelected>>", lambda _event: self._on_exercise_change())

        ttk.Label(control, text="计数侧", style="Panel.TLabel").pack(anchor="w")
        side_box = ttk.Combobox(
            control,
            textvariable=self.side_name,
            values=["自动", "左侧", "右侧"],
            state="readonly",
        )
        side_box.pack(fill=tk.X, pady=(4, 10))

        ttk.Label(control, text="摄像头编号", style="Panel.TLabel").pack(anchor="w")
        ttk.Spinbox(control, from_=0, to=8, textvariable=self.camera_index, width=8).pack(
            fill=tk.X, pady=(4, 10)
        )

        ttk.Label(control, text="模型路径", style="Panel.TLabel").pack(anchor="w")
        model_row = ttk.Frame(control, style="Panel.TFrame")
        model_row.pack(fill=tk.X, pady=(4, 10))
        ttk.Entry(model_row, textvariable=self.model_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(model_row, text="浏览", command=self._browse_model).pack(side=tk.RIGHT, padx=(6, 0))

        ttk.Label(control, text="检测置信度", style="Panel.TLabel").pack(anchor="w")
        conf_row = ttk.Frame(control, style="Panel.TFrame")
        conf_row.pack(fill=tk.X, pady=(4, 10))
        ttk.Scale(conf_row, from_=0.1, to=0.8, variable=self.confidence).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Label(conf_row, textvariable=self.confidence, style="Panel.TLabel", width=5).pack(
            side=tk.RIGHT, padx=(8, 0)
        )

        ttk.Checkbutton(control, text="显示骨架连线", variable=self.show_skeleton).pack(anchor="w", pady=2)
        ttk.Checkbutton(control, text="显示关键点编号", variable=self.show_labels).pack(anchor="w", pady=2)
        ttk.Checkbutton(control, text="镜像摄像头画面", variable=self.mirror_camera).pack(anchor="w", pady=2)

        ttk.Separator(control).pack(fill=tk.X, pady=16)

        ttk.Button(control, text="启动摄像头", style="Accent.TButton", command=self.start).pack(
            fill=tk.X, ipady=6, pady=(0, 8)
        )
        ttk.Button(control, text="停止", command=self.stop).pack(fill=tk.X, ipady=5, pady=(0, 8))
        ttk.Button(control, text="重置计数", command=self.reset_count).pack(fill=tk.X, ipady=5, pady=(0, 8))
        ttk.Button(control, text="退出", command=self.close).pack(fill=tk.X, ipady=5)

        hint = ttk.Label(control, text="", style="Panel.TLabel", wraplength=290, justify=tk.LEFT)
        hint.pack(side=tk.BOTTOM, fill=tk.X, pady=(18, 0))
        self.hint_label = hint

    def _metric_card(self, parent, title, value_var, value_style, row, column):
        card = ttk.Frame(parent, style="Panel.TFrame", padding=8)
        card.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
        parent.columnconfigure(column, weight=1)
        ttk.Label(card, text=title, style="Panel.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=value_var, style=value_style).pack(anchor="w")

    def _browse_model(self):
        path = filedialog.askopenfilename(
            title="选择 YOLO pose 模型",
            filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")],
        )
        if path:
            self.model_path.set(path)
            self.model = None
            self.status_text.set("模型路径已更新，启动时会重新加载")

    def _on_exercise_change(self):
        exercise = self.exercise_name.get()
        self.reset_count()
        if exercise in EXERCISE_STANDARDS:
            self.analyzer = PoseAnalyzer(exercise)
        else:
            self.analyzer = None
        if exercise in EXERCISES:
            config = EXERCISES[exercise]
            self.hint_label.configure(
                text=f"{config.label}：{config.hint}。请让身体尽量完整进入画面，系统会优先跟踪画面中最大的人体。"
            )
        elif exercise in EXERCISE_STANDARDS:
            std = EXERCISE_STANDARDS[exercise]
            self.hint_label.configure(
                text=f"{std.name}：主监测 {std.primary_joint}。请让身体尽量完整进入画面。"
            )
        else:
            self.hint_label.configure(text="")

    def start(self):
        if self.running:
            return

        model_path = Path(self.model_path.get())
        if not model_path.exists():
            messagebox.showerror("模型不存在", f"找不到模型文件：\n{model_path}")
            return

        try:
            if self.model is None:
                self.status_text.set("正在加载 YOLO pose 模型...")
                self.root.update_idletasks()
                self.model = YOLO(str(model_path))

            self.capture = cv2.VideoCapture(int(self.camera_index.get()), cv2.CAP_DSHOW)
            if not self.capture.isOpened():
                self.capture = cv2.VideoCapture(int(self.camera_index.get()))
            if not self.capture.isOpened():
                raise RuntimeError("摄像头打开失败，请检查编号或系统权限")

            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.running = True
            self.last_frame_time = time.time()
            self.status_text.set("检测中")
            self._process_frame()
        except Exception as exc:
            self.stop()
            messagebox.showerror("启动失败", str(exc))

    def stop(self):
        self.running = False
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self.status_text.set("已停止")

    def reset_count(self):
        if self.analyzer is not None:
            self.analyzer.reset()
        self.counter.reset()
        self.count_text.set("0")
        self.phase_text.set("等待")
        self.metric_text.set("-")
        self.score_text.set("--")
        self.angle_score_text.set("--")
        self.temporal_score_text.set("--")
        self.symmetry_score_text.set("--")
        self.hold_time_text.set("0.0s")
        self.errors_text.set("")

    def close(self):
        self.stop()
        self.root.destroy()

    def _process_frame(self):
        if not self.running or self.capture is None:
            return

        ok, frame = self.capture.read()
        if not ok:
            self.status_text.set("读取摄像头画面失败")
            self.stop()
            return

        if self.mirror_camera.get():
            frame = cv2.flip(frame, 1)

        annotated = self._detect_and_draw(frame)
        self._show_frame(annotated)

        now = time.time()
        elapsed = max(now - self.last_frame_time, 1e-6)
        self.fps = 0.85 * self.fps + 0.15 * (1.0 / elapsed) if self.fps else 1.0 / elapsed
        self.last_frame_time = now
        self.fps_text.set(f"{self.fps:.1f}")

        self.root.after(1, self._process_frame)

    def _detect_and_draw(self, frame):
        results = self.model(frame, conf=float(self.confidence.get()), verbose=False)
        if not results:
            return frame

        result = results[0]
        keypoints, confidences = self._select_person(result)
        if keypoints is None:
            self.status_text.set("未检测到人体")
            return frame

        exercise = self.exercise_name.get()
        if self.analyzer is not None:
            analysis = self.analyzer.analyze_frame(keypoints, confidences)
            count = analysis.count
            phase = analysis.phase
            metric = analysis.angles.primary_angle(exercise)
            self.count_text.set(str(count))
            self.phase_text.set(phase)
            self.metric_text.set(self._format_metric(metric, exercise))
            self.score_text.set(f"{analysis.score.total:.0f}")
            self.angle_score_text.set(f"{analysis.score.angle_score:.0f}/40")
            self.temporal_score_text.set(f"{analysis.score.temporal_score:.0f}/30")
            self.symmetry_score_text.set(f"{analysis.score.symmetry_score:.0f}/30")
            self.hold_time_text.set(f"{analysis.hold_time:.1f}s")
            if analysis.errors:
                err_msgs = [f"! {e.name}: {e.suggestion}" for e in analysis.errors]
                self.errors_text.set("\n".join(err_msgs))
                self.errors_label.configure(foreground="#dc2626")
            else:
                self.errors_text.set("无错误，动作标准")
                self.errors_label.configure(foreground="#16a34a")
            self.status_text.set("检测中：姿态分析引擎运行中")
        else:
            # 回退到旧版计数逻辑
            count, phase, metric = self.counter.update(
                exercise, keypoints, confidences, self.side_name.get()
            )
            self.count_text.set(str(count))
            self.phase_text.set(phase)
            self.metric_text.set(self._format_metric(metric, exercise))
            self.score_text.set("--")
            self.angle_score_text.set("--")
            self.temporal_score_text.set("--")
            self.symmetry_score_text.set("--")
            self.hold_time_text.set("--")
            self.errors_text.set("")
            self.status_text.set("检测中：已识别人体关键点")

        if self.show_skeleton.get():
            self._draw_skeleton(frame, keypoints, confidences)
        self._draw_keypoints(frame, keypoints, confidences)
        self._draw_overlay(frame, count, phase, metric, exercise)
        return frame

    def _select_person(self, result):
        if result.keypoints is None or result.keypoints.xy is None:
            return None, None

        xy = result.keypoints.xy.cpu().numpy()
        if len(xy) == 0:
            return None, None

        conf = None
        if result.keypoints.conf is not None:
            conf = result.keypoints.conf.cpu().numpy()

        best_idx = 0
        best_area = -1
        boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None and len(result.boxes) else None
        for i, points in enumerate(xy):
            if boxes is not None and i < len(boxes):
                x1, y1, x2, y2 = boxes[i]
                area = max(0, x2 - x1) * max(0, y2 - y1)
            else:
                visible = points[np.any(points > 0, axis=1)]
                if len(visible) == 0:
                    area = 0
                else:
                    min_xy = visible.min(axis=0)
                    max_xy = visible.max(axis=0)
                    area = np.prod(max_xy - min_xy)
            if area > best_area:
                best_idx = i
                best_area = area

        return xy[best_idx], conf[best_idx] if conf is not None else None

    def _draw_skeleton(self, frame, keypoints, confidences):
        for a, b in SKELETON:
            if valid_point(keypoints, confidences, a) and valid_point(keypoints, confidences, b):
                pa = tuple(np.round(keypoints[a]).astype(int))
                pb = tuple(np.round(keypoints[b]).astype(int))
                cv2.line(frame, pa, pb, (20, 184, 166), 3, cv2.LINE_AA)

    def _draw_keypoints(self, frame, keypoints, confidences):
        for i, point in enumerate(keypoints):
            if not valid_point(keypoints, confidences, i):
                continue
            x, y = np.round(point).astype(int)
            cv2.circle(frame, (x, y), 5, (250, 204, 21), -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), 7, (17, 24, 39), 2, cv2.LINE_AA)
            if self.show_labels.get():
                label = f"{i}:{KEYPOINT_NAMES[i]}"
                cv2.putText(
                    frame,
                    label,
                    (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    frame,
                    label,
                    (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (17, 24, 39),
                    1,
                    cv2.LINE_AA,
                )

    def _draw_overlay(self, frame, count, phase, metric, exercise):
        metric_text = self._format_metric_ascii(metric, exercise)
        exercise_en = EXERCISE_ENGLISH_NAMES.get(exercise, exercise)
        phase_en = PHASE_ENGLISH_NAMES.get(phase, phase)
        lines = [
            f"Action: {exercise_en}",
            f"Count: {count}",
            f"Phase: {phase_en}",
            f"Metric: {metric_text}",
        ]
        # 如果有评分数据显示
        if self.analyzer is not None:
            lines.append(f"Score: {self.score_text.get()}")
        x, y = 18, 28
        box_h = 34 * len(lines) + 18
        cv2.rectangle(frame, (10, 10), (300, box_h), (15, 23, 42), -1)
        cv2.rectangle(frame, (10, 10), (300, box_h), (20, 184, 166), 2)
        for line in lines:
            cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)
            y += 34

    def _format_metric(self, metric, exercise=None):
        if metric is None:
            return "-"
        if exercise is None:
            exercise = self.exercise_name.get()
        if exercise in EXERCISES:
            config = EXERCISES[exercise]
            if config.unit == "state":
                return "打开" if metric > 0.5 else "闭合"
        return f"{metric:.0f}°"

    def _format_metric_ascii(self, metric, exercise=None):
        if metric is None:
            return "-"
        if exercise is None:
            exercise = self.exercise_name.get()
        if exercise in EXERCISES:
            config = EXERCISES[exercise]
            if config.unit == "state":
                return "open" if metric > 0.5 else "closed"
        if exercise == "开合跳":
            return "open" if (metric or 0) > 0.5 else "closed"
        return f"{metric:.0f} deg"

    def _show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)

        label_w = max(self.video_label.winfo_width(), 640)
        label_h = max(self.video_label.winfo_height(), 360)
        image.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)

        self.photo = ImageTk.PhotoImage(image=image)
        self.video_label.configure(image=self.photo, text="")


def run_self_test(model_path):
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"找不到模型文件：{model_path}")
    model = YOLO(str(model_path))
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = model(image, verbose=False, conf=0.25)[0]
    keypoint_shape = None
    if result.keypoints is not None and result.keypoints.xy is not None:
        keypoint_shape = tuple(result.keypoints.xy.shape)
    print(f"模型加载成功：{model_path}")
    print(f"关键点输出形状：{keypoint_shape}")


def main():
    parser = argparse.ArgumentParser(description="健身动作识别计数系统")
    parser.add_argument("--self-test", action="store_true", help="只测试模型加载，不启动 UI")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="YOLO pose 模型路径")
    args = parser.parse_args()

    if args.self_test:
        run_self_test(args.model)
        return

    root = tk.Tk()
    app = WorkoutMonitoringApp(root)
    app.model_path.set(args.model)
    root.mainloop()


if __name__ == "__main__":
    main()
