import argparse
import math
import os
import sys
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from ultralytics import YOLO

# 抑制 OpenCV DSHOW 后端探测警告
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

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
        self.show_debug = tk.BooleanVar(value=True)  # 调试面板开关
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

        # ==== 调试面板: 历史缓冲区 ====
        self._angle_history = deque(maxlen=150)       # EMA 平滑后膝角
        self._raw_angle_history = deque(maxlen=150)   # 原始膝角
        self._knee_left_history = deque(maxlen=150)   # 左膝角
        self._knee_right_history = deque(maxlen=150)  # 右膝角
        self._score_history = deque(maxlen=150)       # 总分
        self._angle_score_hist = deque(maxlen=150)    # 角度得分
        self._temporal_score_hist = deque(maxlen=150) # 时序得分
        self._symmetry_score_hist = deque(maxlen=150) # 对称得分
        self._phase_history = deque(maxlen=150)       # 相位历史
        self._overall_rating_text = ""                 # 最新总体评分文本
        self._overall_rating_timer = 0                 # 总体评分显示倒计时(帧数)

        # ==== 调试面板: 可调参数 (实时生效) ====
        self.debug_angle_tolerance = 10.0        # 角度高斯容差 (°)
        self.debug_symmetry_threshold = 12.0     # 对称性阈值 (°)
        self.debug_smooth_alpha = 0.7            # EMA 平滑系数
        self.debug_low_min = 70.0                # 低位最低有效角度
        self.debug_low_max = 110.0               # 低位最高有效角度
        self.debug_high_min = 155.0              # 高位最低有效角度
        self.debug_high_max = 180.0              # 高位最高有效角度
        self.debug_target_low = 90.0             # 低位目标角度
        self.debug_target_high = 170.0           # 高位目标角度

        self._setup_style()
        self._build_layout()
        self._on_exercise_change()

        # 键盘快捷键绑定
        self.root.bind('<Key>', self._on_key_press)

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

        cam_row = ttk.Frame(control, style="Panel.TFrame")
        cam_row.pack(fill=tk.X, pady=(4, 10))
        ttk.Label(cam_row, text="摄像头编号", style="Panel.TLabel").pack(anchor="w")
        ttk.Spinbox(cam_row, from_=0, to=8, textvariable=self.camera_index, width=5).pack(
            side=tk.LEFT
        )
        ttk.Button(cam_row, text="检测", command=self._detect_cameras, width=5).pack(
            side=tk.RIGHT, padx=(4, 0)
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
        ttk.Checkbutton(control, text="调试面板 (可按键调参)", variable=self.show_debug).pack(anchor="w", pady=2)

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

    def _detect_cameras(self):
        """自动检测可用摄像头并列出分辨率."""
        found = []
        for i in range(9):
            cap = cv2.VideoCapture(i)
            if not cap.isOpened():
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                ok, frame = cap.read()
                brightness = frame.mean() if ok else -1
                found.append((i, w, h, brightness))
                cap.release()
            else:
                found.append((i, 0, 0, -1))

        lines = []
        for i, w, h, b in found:
            if w > 0 and b >= 0:
                status = f"{w}x{h} 亮度={b:.0f}"
            elif w > 0:
                status = f"{w}x{h} 但无法读取画面"
            else:
                status = "不可用"
            lines.append(f"  #{i}: {status}")

        msg = "摄像头检测结果:\n" + "\n".join(lines) + "\n\n请在右侧选择可用的摄像头编号"
        messagebox.showinfo("摄像头检测", msg)

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

            self.capture = cv2.VideoCapture(int(self.camera_index.get()))
            if not self.capture.isOpened():
                self.capture = cv2.VideoCapture(int(self.camera_index.get()), cv2.CAP_DSHOW)
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
        # 清空调试历史
        self._angle_history.clear()
        self._raw_angle_history.clear()
        self._knee_left_history.clear()
        self._knee_right_history.clear()
        self._score_history.clear()
        self._angle_score_hist.clear()
        self._temporal_score_hist.clear()
        self._symmetry_score_hist.clear()
        self._phase_history.clear()
        self._overall_rating_text = ""
        self._overall_rating_timer = 0

    # ================================================================
    # 调试面板 — 数据采集与参数调节
    # ================================================================

    def _collect_debug_data(self, analysis, exercise):
        """采集每帧数据到历史缓冲区."""
        # 膝角数据
        primary = analysis.angles.primary_angle(exercise)
        if primary is not None:
            self._raw_angle_history.append(primary)
            # 从 scorer 内部获取 EMA 平滑后的角度
            if hasattr(self.analyzer, '_scorer') and self.analyzer._scorer._smoothed_angles:
                self._angle_history.append(self.analyzer._scorer._smoothed_angles[-1])
            else:
                self._angle_history.append(primary)
        self._knee_left_history.append(
            analysis.angles.knee_left if analysis.angles.knee_left is not None else 0)
        self._knee_right_history.append(
            analysis.angles.knee_right if analysis.angles.knee_right is not None else 0)
        self._phase_history.append(analysis.phase)

        # 分数数据
        self._score_history.append(analysis.score.total)
        self._angle_score_hist.append(analysis.score.angle_score)
        self._temporal_score_hist.append(analysis.score.temporal_score)
        self._symmetry_score_hist.append(analysis.score.symmetry_score)

        # 总体评分倒计时
        if self._overall_rating_timer > 0:
            self._overall_rating_timer -= 1
        else:
            self._overall_rating_text = ""

    def _apply_debug_params(self):
        """将可调参数实时写入 scorer 和 standard."""
        if self.analyzer is None:
            return
        scorer = self.analyzer._scorer
        standard = self.analyzer.standard

        # 直接修改 scorer 内部参数
        scorer.smooth_alpha = self.debug_smooth_alpha
        scorer.angle_tolerance = self.debug_angle_tolerance
        # 修改 standard 参数 (会影响相位检测和评分)
        standard.low_range = (self.debug_low_min, self.debug_low_max)
        standard.high_range = (self.debug_high_min, self.debug_high_max)
        standard.target_low = self.debug_target_low
        standard.target_high = self.debug_target_high
        standard.symmetry_max_diff = self.debug_symmetry_threshold

    def _draw_debug_panel(self, frame, analysis, exercise):
        """绘制完整的调试面板叠加层."""
        h, w = frame.shape[:2]

        # ── 左上: 增强信息面板 ──
        self._draw_info_panel(frame, analysis, exercise)

        # ── 右上: 角度历史曲线 ──
        chart_w, chart_h = 260, 140
        self._draw_angle_chart(frame, w - chart_w - 12, 12, chart_w, chart_h)

        # ── 右中: 分数历史曲线 ──
        self._draw_score_chart(frame, w - chart_w - 12, 164, chart_w, 120)

        # ── 右下: 左右膝角对比条 ──
        self._draw_symmetry_gauge(frame, w - chart_w - 12, 296, chart_w, 60, analysis)

        # ── 底部: 键盘快捷键栏 ──
        self._draw_keybind_bar(frame)

        # ── 总体评分弹窗 ──
        if self._overall_rating_text and self._overall_rating_timer > 0:
            self._draw_overall_popup(frame)

    def _draw_info_panel(self, frame, analysis, exercise):
        """左上角信息面板 — 角度详情 + 得分细分."""
        std = self.analyzer.standard if self.analyzer else None

        lines = []
        # 动作 + 计数 + 相位
        phase = analysis.phase
        phase_color = {
            "高位": (100, 255, 100), "低位": (100, 180, 255),
            "保持": (255, 200, 100), "等待": (180, 180, 180),
            "姿态调整": (255, 150, 100),
        }.get(phase, (255, 255, 255))

        lines.append(("count", f"┃ {exercise}  #{analysis.count}"))
        lines.append(("phase", f"┃ 相位: {phase}"))
        lines.append(("angle", f"┃ 膝角均值: {self._format_metric(analysis.angles.primary_angle(exercise), exercise)}"))
        if analysis.angles.knee_left is not None and analysis.angles.knee_right is not None:
            lines.append(("lr", f"┃   L: {analysis.angles.knee_left:.0f}°  R: {analysis.angles.knee_right:.0f}°"))
        if std:
            if phase in ("低位", "保持"):
                tgt = self.debug_target_low
                rng = (self.debug_low_min, self.debug_low_max)
            else:
                tgt = self.debug_target_high
                rng = (self.debug_high_min, self.debug_high_max)
            lines.append(("target", f"┃ 目标: {tgt:.0f}°  范围: [{rng[0]:.0f}, {rng[1]:.0f}]"))
        lines.append(("sep1", "┃ ─────────────────"))
        lines.append(("score", f"┃ 总分: {analysis.score.total:.0f}/100"))
        lines.append(("angle_s", f"┃  角度 {analysis.score.angle_score:.0f}/40  "
                   f"({analysis.score.angle_score/40*100:.0f}%)"))
        lines.append(("temp_s", f"┃  时序 {analysis.score.temporal_score:.0f}/30  "
                   f"({analysis.score.temporal_score/30*100:.0f}%)"))
        lines.append(("sym_s",  f"┃  对称 {analysis.score.symmetry_score:.0f}/30  "
                   f"({analysis.score.symmetry_score/30*100:.0f}%)"))

        # 绘制面板背景
        n = len(lines)
        panel_h = 20 * n + 20
        panel_w = 310
        x, y = 10, 10
        cv2.rectangle(frame, (x, y), (x + panel_w, y + panel_h), (15, 23, 42), -1)
        cv2.rectangle(frame, (x, y), (x + panel_w, y + panel_h), (60, 60, 80), 1)

        y_offset = y + 18
        for key, text in lines:
            if key == "sep1":
                y_offset += 6
                cv2.line(frame, (x + 14, y_offset), (x + panel_w - 14, y_offset),
                         (60, 60, 80), 1)
                y_offset += 6
                continue
            if key == "phase":
                color = phase_color
            elif key == "score":
                s = analysis.score.total
                if s >= 85:
                    color = (100, 255, 100)
                elif s >= 70:
                    color = (200, 255, 100)
                elif s >= 50:
                    color = (100, 200, 255)
                else:
                    color = (100, 100, 255)
            elif key in ("angle_s", "temp_s", "sym_s"):
                if key == "angle_s":
                    pct = analysis.score.angle_score / 40
                elif key == "temp_s":
                    pct = analysis.score.temporal_score / 30
                else:
                    pct = analysis.score.symmetry_score / 30
                if pct >= 0.85:
                    color = (100, 255, 100)
                elif pct >= 0.60:
                    color = (100, 200, 255)
                else:
                    color = (100, 100, 255)
            else:
                color = (220, 220, 220)

            cv2.putText(frame, text, (x + 12, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, color, 1, cv2.LINE_AA)
            y_offset += 20

    def _draw_angle_chart(self, frame, x, y, w, h):
        """右上: 膝角历史曲线 (原始 + 平滑)."""
        # 背景
        cv2.rectangle(frame, (x, y), (x + w, y + h), (18, 25, 45), -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 70, 100), 1)

        # 标题
        cv2.putText(frame, "Knee Angle", (x + 6, y + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        plot_x, plot_y = x + 8, y + 24
        plot_w, plot_h = w - 16, h - 42

        # 目标区域 (高位绿带, 低位蓝带)
        high_min_y = self._angle_to_y(plot_y, plot_h, self.debug_high_min, 60, 180)
        high_max_y = self._angle_to_y(plot_y, plot_h, self.debug_high_max, 60, 180)
        low_min_y = self._angle_to_y(plot_y, plot_h, self.debug_low_min, 60, 180)
        low_max_y = self._angle_to_y(plot_y, plot_h, self.debug_low_max, 60, 180)

        # 高位目标带 (绿色半透明)
        overlay = frame.copy()
        cv2.rectangle(overlay, (plot_x, high_max_y), (plot_x + plot_w, high_min_y),
                      (40, 80, 40), -1)
        frame[:] = cv2.addWeighted(frame, 0.85, overlay, 0.15, 0)
        # 低位目标带 (蓝色半透明)
        overlay2 = frame.copy()
        cv2.rectangle(overlay2, (plot_x, low_max_y), (plot_x + plot_w, low_min_y),
                      (60, 40, 20), -1)
        frame[:] = cv2.addWeighted(frame, 0.85, overlay2, 0.15, 0)

        # 目标线
        tgt_high_y = self._angle_to_y(plot_y, plot_h, self.debug_target_high, 60, 180)
        tgt_low_y = self._angle_to_y(plot_y, plot_h, self.debug_target_low, 60, 180)
        cv2.line(frame, (plot_x, tgt_high_y), (plot_x + plot_w, tgt_high_y),
                 (80, 180, 80), 1, cv2.LINE_AA)
        cv2.line(frame, (plot_x, tgt_low_y), (plot_x + plot_w, tgt_low_y),
                 (180, 120, 60), 1, cv2.LINE_AA)

        # 原始角度线 (细, 半透明)
        self._draw_line_series(frame, plot_x, plot_y, plot_w, plot_h,
                               self._raw_angle_history, (100, 120, 150), 1, 60, 180)
        # 平滑角度线 (粗, 亮色)
        self._draw_line_series(frame, plot_x, plot_y, plot_w, plot_h,
                               self._angle_history, (80, 220, 255), 2, 60, 180)

        # 图例
        ly = y + h - 10
        cv2.line(frame, (x + 8, ly), (x + 28, ly), (100, 120, 150), 1)
        cv2.putText(frame, "raw", (x + 32, ly + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
        cv2.line(frame, (x + 68, ly), (x + 88, ly), (80, 220, 255), 2)
        cv2.putText(frame, "smooth", (x + 92, ly + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
        # 当前值
        if self._angle_history:
            val = self._angle_history[-1]
            cv2.putText(frame, f"{val:.0f}", (x + w - 40, ly + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 220, 255), 1, cv2.LINE_AA)

    def _draw_score_chart(self, frame, x, y, w, h):
        """右中: 分数历史曲线."""
        # 背景
        cv2.rectangle(frame, (x, y), (x + w, y + h), (18, 25, 45), -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 70, 100), 1)

        # 标题
        cv2.putText(frame, "Score", (x + 6, y + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        plot_x, plot_y = x + 8, y + 22
        plot_w, plot_h = w - 16, h - 36

        # 得分区背景 (绿/黄/红 横带)
        overlay = frame.copy()
        # >= 85 绿色带
        good_y = plot_y + int(plot_h * 0.15)
        cv2.rectangle(overlay, (plot_x, plot_y), (plot_x + plot_w, good_y),
                      (20, 70, 20), -1)
        # 50-85 黄色带
        mid_y = plot_y + int(plot_h * 0.50)
        cv2.rectangle(overlay, (plot_x, good_y), (plot_x + plot_w, mid_y),
                      (40, 40, 15), -1)
        # < 50 红色带
        cv2.rectangle(overlay, (plot_x, mid_y), (plot_x + plot_w, plot_y + plot_h),
                      (40, 15, 15), -1)
        frame[:] = cv2.addWeighted(frame, 0.92, overlay, 0.08, 0)

        # 分数线
        self._draw_line_series(frame, plot_x, plot_y, plot_w, plot_h,
                               self._score_history, (100, 255, 180), 2, 0, 100)
        # 角度得分线
        self._draw_line_series(frame, plot_x, plot_y + 1, plot_w, plot_h,
                               [v / 40.0 * 100 for v in self._angle_score_hist],
                               (120, 200, 255), 1, 0, 100)
        # 对称得分线
        self._draw_line_series(frame, plot_x, plot_y + 1, plot_w, plot_h,
                               [v / 30.0 * 100 for v in self._symmetry_score_hist],
                               (200, 160, 255), 1, 0, 100)

        # 图例
        ly = y + h - 6
        cv2.line(frame, (x + 8, ly), (x + 20, ly), (100, 255, 180), 2)
        cv2.putText(frame, "tot", (x + 22, ly + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (150, 150, 150), 1)
        cv2.line(frame, (x + 50, ly), (x + 62, ly), (120, 200, 255), 1)
        cv2.putText(frame, "ang", (x + 64, ly + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (150, 150, 150), 1)
        cv2.line(frame, (x + 92, ly), (x + 104, ly), (200, 160, 255), 1)
        cv2.putText(frame, "sym", (x + 106, ly + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (150, 150, 150), 1)
        # 当前分数
        if self._score_history:
            val = self._score_history[-1]
            color = (100, 255, 100) if val >= 85 else (200, 255, 100) if val >= 70 else (100, 200, 255) if val >= 50 else (150, 100, 255)
            cv2.putText(frame, f"{val:.0f}", (x + w - 35, ly + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    def _draw_symmetry_gauge(self, frame, x, y, w, h, analysis):
        """右下: 左右膝角实时对比条."""
        cv2.rectangle(frame, (x, y), (x + w, y + h), (18, 25, 45), -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 70, 100), 1)

        cv2.putText(frame, "L/R Knee", (x + 6, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 200, 200), 1, cv2.LINE_AA)

        # 左膝条
        bar_x, bar_y = x + 14, y + 22
        bar_w, bar_h = w - 28, 12
        l_val = analysis.angles.knee_left or 0
        r_val = analysis.angles.knee_right or 0
        l_pct = max(0, min(1.0, l_val / 180.0))
        r_pct = max(0, min(1.0, r_val / 180.0))

        # 左膝
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                      (50, 50, 50), -1)
        cv2.rectangle(frame, (bar_x, bar_y),
                      (bar_x + int(bar_w * l_pct), bar_y + bar_h),
                      (255, 150, 50), -1)
        cv2.putText(frame, f"L: {l_val:.0f}", (bar_x + 4, bar_y + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        # 右膝
        bar_y2 = bar_y + bar_h + 5
        cv2.rectangle(frame, (bar_x, bar_y2), (bar_x + bar_w, bar_y2 + bar_h),
                      (50, 50, 50), -1)
        cv2.rectangle(frame, (bar_x, bar_y2),
                      (bar_x + int(bar_w * r_pct), bar_y2 + bar_h),
                      (50, 180, 255), -1)
        cv2.putText(frame, f"R: {r_val:.0f}", (bar_x + 4, bar_y2 + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        # 差异提示
        if l_val > 0 and r_val > 0:
            diff = abs(l_val - r_val)
            diff_color = (100, 255, 100) if diff < self.debug_symmetry_threshold else (100, 100, 255)
            cv2.putText(frame, f"diff: {diff:.0f} (limit: {self.debug_symmetry_threshold:.0f})",
                        (bar_x, bar_y2 + bar_h + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, diff_color, 1, cv2.LINE_AA)

    def _draw_keybind_bar(self, frame):
        """底部: 键盘快捷键提示条."""
        h, w = frame.shape[:2]
        bar_h = 24
        y = h - bar_h

        cv2.rectangle(frame, (0, y), (w, h), (10, 15, 30), -1)
        cv2.line(frame, (0, y), (w, y), (60, 70, 100), 1)

        keys = [
            "[1/2]容差", "[3/4]对称阈值", "[5/6]EMA",
            "[7/8]低位", "[9/0]高位", "[O]总体评分",
            "[R]重置", "[D]面板开关", "[Q]退出",
        ]
        x_off = 8
        for key_text in keys:
            (tw, th), _ = cv2.getTextSize(key_text, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
            cv2.putText(frame, key_text, (x_off, y + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 190, 210), 1, cv2.LINE_AA)
            x_off += tw + 12

    def _draw_overall_popup(self, frame):
        """总体评分弹窗 (居中)."""
        h, w = frame.shape[:2]
        lines = self._overall_rating_text.split('\n')
        line_h = 26
        popup_h = len(lines) * line_h + 40
        popup_w = 420
        px, py = (w - popup_w) // 2, (h - popup_h) // 2

        # 背景
        cv2.rectangle(frame, (px, py), (px + popup_w, py + popup_h), (20, 25, 50), -1)
        cv2.rectangle(frame, (px, py), (px + popup_w, py + popup_h), (100, 200, 150), 2)

        y_off = py + 24
        for line in lines:
            cv2.putText(frame, line, (px + 16, y_off),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (230, 240, 255), 1, cv2.LINE_AA)
            y_off += line_h

    # ================================================================
    # 调试面板 — 绘图工具函数
    # ================================================================

    @staticmethod
    def _draw_line_series(frame, px, py, pw, ph, data, color, thickness, y_min, y_max):
        """在指定区域绘制折线图."""
        if len(data) < 2:
            return
        pts = []
        y_range = max(y_max - y_min, 1.0)
        for i, v in enumerate(data):
            x = px + int(pw * i / (len(data) - 1))
            y_clamped = max(y_min, min(y_max, v))
            y = py + int(ph * (1.0 - (y_clamped - y_min) / y_range))
            pts.append([x, y])
        pts_arr = np.array(pts, dtype=np.int32)
        cv2.polylines(frame, [pts_arr], False, color, thickness, cv2.LINE_AA)

    @staticmethod
    def _angle_to_y(py, ph, angle, y_min, y_max):
        """角度值 → 像素 y 坐标."""
        y_range = max(y_max - y_min, 1.0)
        a = max(y_min, min(y_max, angle))
        return py + int(ph * (1.0 - (a - y_min) / y_range))

    # ================================================================
    # 调试面板 — 键盘处理
    # ================================================================

    def _on_key_press(self, event):
        """键盘快捷键处理."""
        key = event.char.lower() if event.char else event.keysym

        if key == 'd':
            # 切换调试面板
            self.show_debug.set(not self.show_debug.get())
        elif key == 'r':
            self.reset_count()
        elif key == 'q':
            self.close()
        elif key == '1':
            self.debug_angle_tolerance = max(1.0, self.debug_angle_tolerance - 1)
        elif key == '2':
            self.debug_angle_tolerance = min(30.0, self.debug_angle_tolerance + 1)
        elif key == '3':
            self.debug_symmetry_threshold = max(3.0, self.debug_symmetry_threshold - 1)
        elif key == '4':
            self.debug_symmetry_threshold = min(30.0, self.debug_symmetry_threshold + 1)
        elif key == '5':
            self.debug_smooth_alpha = max(0.1, round(self.debug_smooth_alpha - 0.05, 2))
        elif key == '6':
            self.debug_smooth_alpha = min(1.0, round(self.debug_smooth_alpha + 0.05, 2))
        elif key == '7':
            self.debug_low_min = max(40.0, self.debug_low_min - 2)
        elif key == '8':
            self.debug_low_max = min(130.0, self.debug_low_max + 2)
        elif key == '9':
            self.debug_high_min = max(130.0, self.debug_high_min - 2)
        elif key == '0':
            self.debug_high_max = min(190.0, self.debug_high_max + 2)
        elif key == 'o':
            # 显示总体评分报告
            if self.analyzer is not None:
                overall = self.analyzer.get_overall_rating()
                self._overall_rating_text = (
                    f"🏆 总体评分报告\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"综合评分: {overall.total_score:.0f}/100  {overall.grade_emoji} {overall.grade}\n"
                    f"趋势: {overall.trend}   总次数: {overall.total_reps}   时长: {overall.total_duration_seconds:.0f}s\n"
                    f"分维度: {overall.dimension_breakdown}\n"
                    f"亮点: {overall.highlight}   短板: {overall.weakness}\n"
                    f"建议: {overall.suggestion}"
                )
                self._overall_rating_timer = 180  # 显示 180 帧 (~6秒 @30fps)

        # 更新键盘栏中显示的可调参数值
        self._update_keybind_bar_text()

    def _update_keybind_bar_text(self):
        """将当前参数值反映到状态栏 (通过 status_text)."""
        params = (
            f"容差={self.debug_angle_tolerance:.0f} "
            f"对称={self.debug_symmetry_threshold:.0f} "
            f"EMA={self.debug_smooth_alpha:.2f} "
            f"低位=[{self.debug_low_min:.0f},{self.debug_low_max:.0f}] "
            f"高位=[{self.debug_high_min:.0f},{self.debug_high_max:.0f}]"
        )
        if self.running:
            self.status_text.set(f"检测中 | {params}")

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

        # ==== 调试面板 ====
        if self.show_debug.get() and self.analyzer is not None:
            # 采集历史数据
            self._collect_debug_data(analysis, exercise)
            # 应用可调参数到 scorer
            self._apply_debug_params()
            # 绘制调试面板
            self._draw_debug_panel(frame, analysis, exercise)

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
