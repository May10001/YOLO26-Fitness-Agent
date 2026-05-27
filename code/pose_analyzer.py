"""
YOLO26 居家健身姿态分析引擎
==============================
C成员第一阶段工作：
  1. 17个人体关键点 → 关节角度 + 时序特征
  2. 5个核心动作标准参数阈值
  3. 动作评分算法 (0-100, 三维度)
  4. 5类常见错误动作识别
"""

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

# ============================================================================
# 常量定义 — 与 YOLO26 COCO 17 关键点一致
# ============================================================================

KEYPOINT_NAMES = [
    "nose",            # 0
    "left_eye",        # 1
    "right_eye",       # 2
    "left_ear",        # 3
    "right_ear",       # 4
    "left_shoulder",   # 5
    "right_shoulder",  # 6
    "left_elbow",      # 7
    "right_elbow",     # 8
    "left_wrist",      # 9
    "right_wrist",     # 10
    "left_hip",        # 11
    "right_hip",       # 12
    "left_knee",       # 13
    "right_knee",      # 14
    "left_ankle",      # 15
    "right_ankle",     # 16
]

# 骨架连线
SKELETON = [
    (5, 7), (7, 9),   # 左臂
    (6, 8), (8, 10),  # 右臂
    (5, 6),            # 肩连线
    (5, 11), (6, 12), # 躯干
    (11, 12),          # 髋连线
    (11, 13), (13, 15), # 左腿
    (12, 14), (14, 16), # 右腿
    (0, 1), (0, 2),   # 面部
    (1, 3), (2, 4),
]

# 左右侧关键点三元组: (近端, 关节, 远端)
SIDE_TRIPLETS = {
    "left": {
        "elbow":    (5, 7, 9),
        "knee":     (11, 13, 15),
        "hip":      (5, 11, 13),
        "shoulder": (7, 5, 11),
        "ankle":    (13, 15, None),  # 特殊: 膝-踝-垂直
    },
    "right": {
        "elbow":    (6, 8, 10),
        "knee":     (12, 14, 16),
        "hip":      (6, 12, 14),
        "shoulder": (8, 6, 12),
        "ankle":    (14, 16, None),
    },
}


# ============================================================================
# 基础几何运算
# ============================================================================

def calculate_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """计算三点夹角 ∠ABC (B为顶点), 返回 0~180 度."""
    a, b, c = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32), np.asarray(c, dtype=np.float32)
    radians = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
    angle = abs(radians * 180.0 / math.pi)
    return 360.0 - angle if angle > 180.0 else angle


def calculate_vertical_angle(a: np.ndarray, b: np.ndarray) -> float:
    """计算向量 AB 与垂直向下方向 (0, 1) 的夹角, 返回 0~180 度."""
    a, b = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    vec = b - a
    norm = np.linalg.norm(vec)
    if norm < 1e-6:
        return 0.0
    cos_theta = vec[1] / norm  # 与垂直向下的点积
    cos_theta = max(-1.0, min(1.0, cos_theta))
    return math.degrees(math.acos(cos_theta))


def point_distance(a: np.ndarray, b: np.ndarray) -> float:
    """两点欧氏距离."""
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


def point_to_line_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """点 p 到线段 ab 的垂直距离."""
    p, a, b = np.asarray(p), np.asarray(a), np.asarray(b)
    ab = b - a
    ap = p - a
    ab_norm = np.linalg.norm(ab)
    if ab_norm < 1e-6:
        return float(np.linalg.norm(ap))
    # 2D cross product: ab_x * ap_y - ab_y * ap_x
    cross = ab[0] * ap[1] - ab[1] * ap[0]
    return float(abs(cross) / ab_norm)


def valid_point(keypoints: np.ndarray, confidences: Optional[np.ndarray],
                idx: int, min_conf: float = 0.15) -> bool:
    """判断关键点是否有效."""
    if idx >= len(keypoints):
        return False
    x, y = keypoints[idx]
    if x <= 0 and y <= 0:
        return False
    if confidences is not None and confidences[idx] < min_conf:
        return False
    return True


# ============================================================================
# 数据结构定义
# ============================================================================

@dataclass
class JointAngles:
    """单帧所有关节角度."""
    knee_left: Optional[float] = None
    knee_right: Optional[float] = None
    hip_left: Optional[float] = None
    hip_right: Optional[float] = None
    elbow_left: Optional[float] = None
    elbow_right: Optional[float] = None
    shoulder_left: Optional[float] = None
    shoulder_right: Optional[float] = None
    trunk_angle: Optional[float] = None
    ankle_left: Optional[float] = None
    ankle_right: Optional[float] = None

    def mean_symmetric(self, attr: str) -> Optional[float]:
        """取左右侧均值."""
        l = getattr(self, f"{attr}_left")
        r = getattr(self, f"{attr}_right")
        vals = [v for v in (l, r) if v is not None]
        return float(np.mean(vals)) if vals else None

    def diff_symmetric(self, attr: str) -> Optional[float]:
        """取左右侧差值绝对值."""
        l = getattr(self, f"{attr}_left")
        r = getattr(self, f"{attr}_right")
        if l is not None and r is not None:
            return abs(l - r)
        return None

    def primary_angle(self, exercise: str) -> Optional[float]:
        """根据动作类型返回主角度."""
        primary_map = {
            "深蹲":       self.mean_symmetric("knee"),
            "俯卧撑":     self.mean_symmetric("elbow"),
            "平板支撑":   self.mean_symmetric("elbow"),
            "卷腹":       self.trunk_angle,
            "开合跳":     None,  # 开合跳用肢体展开状态
            "引体向上":   self.mean_symmetric("elbow"),
            "臀桥":       self.mean_symmetric("hip"),
            "高抬腿":     self.mean_symmetric("hip"),
            "肩推":       self.mean_symmetric("elbow"),
            "侧平举":     self.mean_symmetric("shoulder"),
        }
        return primary_map.get(exercise)


@dataclass
class TemporalFeatures:
    """时序特征."""
    angular_velocity: float = 0.0       # 角速度 (°/s)
    smoothness: float = 0.0             # 平滑度 (jerk std, 越小越平滑)
    rhythm_consistency: float = 0.0     # 节奏一致性 (rep时长CV, 越小越一致)
    rom_consistency: float = 0.0        # 动作幅度一致性 (越小越一致)


@dataclass
class ExerciseStandard:
    """动作标准参数."""
    name: str                           # 动作名称
    primary_joint: str                  # 主监测关节
    target_low: float                   # 低位目标角度
    target_high: float                  # 高位目标角度
    low_range: Tuple[float, float]      # 低位有效范围 (min, max)
    high_range: Tuple[float, float]     # 高位有效范围 (min, max)
    count_trigger: str                  # "high" 或 "low"
    trunk_max: float                    # 躯干最大允许角度
    symmetry_joints: Tuple[str, ...]    # 需检查对称性的关节
    symmetry_max_diff: float            # 最大允许左右差异 (°)
    hold_threshold: Optional[float] = None  # 平板支撑等静态动作保持阈值


@dataclass
class ErrorInfo:
    """错误动作信息."""
    name: str                           # 错误名称
    severity: int                       # 严重程度 1-3
    message: str                        # 实时反馈消息
    suggestion: str                     # 修正建议


@dataclass
class ScoreResult:
    """评分结果."""
    total: float = 0.0                  # 总分 0-100
    angle_score: float = 0.0            # 关节角度得分 0-40
    temporal_score: float = 0.0         # 时序一致性得分 0-30
    symmetry_score: float = 0.0         # 对称性得分 0-30


@dataclass
class AnalysisResult:
    """每帧分析结果."""
    angles: JointAngles = field(default_factory=JointAngles)
    temporal: TemporalFeatures = field(default_factory=TemporalFeatures)
    phase: str = "等待"
    count: int = 0
    hold_time: float = 0.0              # 平板支撑等动作的保持时间
    errors: list = field(default_factory=list)
    score: ScoreResult = field(default_factory=ScoreResult)


# ============================================================================
# 1. 关节角度提取器
# ============================================================================

class JointAngleExtractor:
    """从 YOLO26 输出的 17 个关键点提取全部关节角度."""

    def extract(self, keypoints: np.ndarray,
                confidences: Optional[np.ndarray] = None) -> JointAngles:
        angles = JointAngles()

        angles.knee_left   = self._joint_angle(keypoints, confidences, "knee", "left")
        angles.knee_right  = self._joint_angle(keypoints, confidences, "knee", "right")
        angles.hip_left    = self._joint_angle(keypoints, confidences, "hip", "left")
        angles.hip_right   = self._joint_angle(keypoints, confidences, "hip", "right")
        angles.elbow_left  = self._joint_angle(keypoints, confidences, "elbow", "left")
        angles.elbow_right = self._joint_angle(keypoints, confidences, "elbow", "right")
        angles.shoulder_left  = self._joint_angle(keypoints, confidences, "shoulder", "left")
        angles.shoulder_right = self._joint_angle(keypoints, confidences, "shoulder", "right")
        angles.ankle_left  = self._ankle_vertical_angle(keypoints, confidences, "left")
        angles.ankle_right = self._ankle_vertical_angle(keypoints, confidences, "right")
        angles.trunk_angle = self._trunk_vertical_angle(keypoints, confidences)

        return angles

    def _joint_angle(self, keypoints, confidences, joint_name: str,
                     side: str) -> Optional[float]:
        """通用关节角度计算."""
        ids = SIDE_TRIPLETS[side][joint_name]
        if joint_name == "ankle":
            return self._ankle_vertical_angle(keypoints, confidences, side)
        if all(valid_point(keypoints, confidences, i) for i in ids):
            return calculate_angle(keypoints[ids[0]], keypoints[ids[1]], keypoints[ids[2]])
        return None

    def _ankle_vertical_angle(self, keypoints, confidences, side: str) -> Optional[float]:
        """踝关节角度: 膝-踝连线与垂直线的夹角."""
        ids = SIDE_TRIPLETS[side]["ankle"]  # (knee, ankle, None)
        knee_idx, ankle_idx = ids[0], ids[1]
        if valid_point(keypoints, confidences, knee_idx) and valid_point(keypoints, confidences, ankle_idx):
            return calculate_vertical_angle(keypoints[knee_idx], keypoints[ankle_idx])
        return None

    def _trunk_vertical_angle(self, keypoints, confidences) -> Optional[float]:
        """躯干倾角: 肩中点→髋中点 与垂直线的夹角."""
        shoulder_ids = [5, 6]
        hip_ids = [11, 12]
        if all(valid_point(keypoints, confidences, i) for i in shoulder_ids + hip_ids):
            shoulder_mid = (keypoints[5] + keypoints[6]) / 2
            hip_mid = (keypoints[11] + keypoints[12]) / 2
            return calculate_vertical_angle(hip_mid, shoulder_mid)
        return None


# ============================================================================
# 2. 时序特征提取器
# ============================================================================

class TemporalFeatureExtractor:
    """滑动窗口时序特征提取.

    默认窗口 90 帧 (约 3 秒 @ 30fps).
    """

    def __init__(self, window_size: int = 90):
        self.window_size = window_size
        self.angle_history: deque = deque(maxlen=window_size)
        self.timestamp_history: deque = deque(maxlen=window_size)
        self.rep_durations: list = []  # 已完成 rep 的时长记录
        self.rep_peaks: list = []      # rep peak 值记录
        self._last_phase: str = "等待"
        self._rep_start_time: Optional[float] = None

    def update(self, angle_value: Optional[float], phase: str,
               timestamp: Optional[float] = None) -> TemporalFeatures:
        """添加一帧数据并返回当前时序特征."""
        if timestamp is None:
            timestamp = time.time()

        if angle_value is not None:
            self.angle_history.append(angle_value)
            self.timestamp_history.append(timestamp)
        else:
            self.angle_history.append(self.angle_history[-1] if self.angle_history else 0.0)
            self.timestamp_history.append(timestamp)

        # rep 计时
        self._track_rep(phase, timestamp)

        return TemporalFeatures(
            angular_velocity=self._calc_velocity(),
            smoothness=self._calc_smoothness(),
            rhythm_consistency=self._calc_rhythm_consistency(),
            rom_consistency=self._calc_rom_consistency(),
        )

    def _track_rep(self, phase: str, timestamp: float):
        """追踪 rep 开始/结束及运动幅度."""
        # rep 完成: 低位→高位
        if self._last_phase == "低位" and phase == "高位":
            if self._rep_start_time is not None:
                duration = timestamp - self._rep_start_time
                self.rep_durations.append(duration)
            self._rep_start_time = None
            # 记录本次 rep 的峰值 (angle_history 最大值)
            if len(self.angle_history) > 0:
                self.rep_peaks.append(max(self.angle_history))
        elif self._last_phase == "高位" and phase == "低位":
            self._rep_start_time = timestamp
        self._last_phase = phase

    def _calc_velocity(self) -> float:
        """角速度 (°/s): 最近两帧的变化率."""
        if len(self.angle_history) < 2 or len(self.timestamp_history) < 2:
            return 0.0
        da = self.angle_history[-1] - self.angle_history[-2]
        dt = max(self.timestamp_history[-1] - self.timestamp_history[-2], 1e-6)
        return abs(da / dt)

    def _calc_smoothness(self) -> float:
        """平滑度: 角加速度 (jerk) 的标准差, 越小越平滑."""
        if len(self.angle_history) < 3:
            return 0.0
        vel = np.diff(list(self.angle_history))
        if len(vel) < 2:
            return 0.0
        acc = np.diff(vel)
        return float(np.std(acc))

    def _calc_rhythm_consistency(self) -> float:
        """节奏一致性: rep 持续时间的变异系数 (CV), 0 表示完美一致."""
        if len(self.rep_durations) < 2:
            return 0.0
        durations = np.array(self.rep_durations[-10:])  # 最近 10 个 rep
        mean_d = np.mean(durations)
        if mean_d < 1e-6:
            return 0.0
        return float(np.std(durations) / mean_d)

    def _calc_rom_consistency(self) -> float:
        """动作幅度一致性: rep peak 值的变异系数."""
        if len(self.rep_peaks) < 2:
            return 0.0
        peaks = np.array(self.rep_peaks[-10:])
        mean_p = np.mean(peaks)
        if mean_p < 1e-6:
            return 0.0
        return float(np.std(peaks) / mean_p)

    def reset(self):
        self.angle_history.clear()
        self.timestamp_history.clear()
        self.rep_durations.clear()
        self.rep_peaks.clear()
        self._last_phase = "等待"
        self._rep_start_time = None


# ============================================================================
# 3. 五类核心动作标准参数
# ============================================================================

EXERCISE_STANDARDS: dict[str, ExerciseStandard] = {
    "深蹲": ExerciseStandard(
        name="深蹲",
        primary_joint="knee_angle",
        target_low=90.0,
        target_high=170.0,
        low_range=(70.0, 110.0),
        high_range=(155.0, 180.0),
        count_trigger="high",
        trunk_max=35.0,
        symmetry_joints=("knee",),
        symmetry_max_diff=12.0,
    ),
    "俯卧撑": ExerciseStandard(
        name="俯卧撑",
        primary_joint="elbow_angle",
        target_low=90.0,
        target_high=170.0,
        low_range=(70.0, 110.0),
        high_range=(155.0, 180.0),
        count_trigger="high",
        trunk_max=20.0,
        symmetry_joints=("elbow", "shoulder"),
        symmetry_max_diff=12.0,
    ),
    "平板支撑": ExerciseStandard(
        name="平板支撑",
        primary_joint="elbow_angle",
        target_low=90.0,
        target_high=90.0,
        low_range=(70.0, 110.0),
        high_range=(70.0, 110.0),
        count_trigger="high",       # 不用计数, 计时
        trunk_max=12.0,
        symmetry_joints=("elbow", "knee"),
        symmetry_max_diff=10.0,
        hold_threshold=90.0,
    ),
    "卷腹": ExerciseStandard(
        name="卷腹",
        primary_joint="trunk_angle",
        target_low=40.0,
        target_high=5.0,
        low_range=(25.0, 55.0),
        high_range=(0.0, 15.0),
        count_trigger="high",
        trunk_max=55.0,
        symmetry_joints=("shoulder",),
        symmetry_max_diff=15.0,
    ),
    "开合跳": ExerciseStandard(
        name="开合跳",
        primary_joint="spread_state",
        target_low=0.0,
        target_high=1.0,
        low_range=(-0.1, 0.3),
        high_range=(0.7, 1.1),
        count_trigger="high",
        trunk_max=25.0,
        symmetry_joints=("elbow", "knee"),
        symmetry_max_diff=20.0,
    ),
    "引体向上": ExerciseStandard(
        name="引体向上",
        primary_joint="elbow_angle",
        target_low=160.0,
        target_high=55.0,
        low_range=(140.0, 180.0),
        high_range=(35.0, 80.0),
        count_trigger="high",
        trunk_max=15.0,
        symmetry_joints=("elbow", "shoulder"),
        symmetry_max_diff=10.0,
    ),
    "臀桥": ExerciseStandard(
        name="臀桥",
        primary_joint="hip_angle",
        target_low=100.0,
        target_high=175.0,
        low_range=(80.0, 125.0),
        high_range=(165.0, 180.0),
        count_trigger="high",
        trunk_max=20.0,
        symmetry_joints=("knee", "hip"),
        symmetry_max_diff=12.0,
    ),
    "高抬腿": ExerciseStandard(
        name="高抬腿",
        primary_joint="hip_angle",
        target_low=170.0,
        target_high=95.0,
        low_range=(150.0, 180.0),
        high_range=(70.0, 115.0),
        count_trigger="high",
        trunk_max=15.0,
        symmetry_joints=("knee", "hip"),
        symmetry_max_diff=15.0,
    ),
    "肩推": ExerciseStandard(
        name="肩推",
        primary_joint="elbow_angle",
        target_low=70.0,
        target_high=170.0,
        low_range=(50.0, 90.0),
        high_range=(155.0, 180.0),
        count_trigger="high",
        trunk_max=15.0,
        symmetry_joints=("elbow", "shoulder"),
        symmetry_max_diff=12.0,
    ),
    "侧平举": ExerciseStandard(
        name="侧平举",
        primary_joint="shoulder_angle",
        target_low=10.0,
        target_high=90.0,
        low_range=(0.0, 30.0),
        high_range=(75.0, 105.0),
        count_trigger="high",
        trunk_max=12.0,
        symmetry_joints=("elbow", "shoulder"),
        symmetry_max_diff=12.0,
    ),
}


# ============================================================================
# 4. 动作评分算法
# ============================================================================

class MovementScorer:
    """三维度动作评分器 (0-100 分).

    - 关节角度得分: 0-40 分 (目标角度接近度)
    - 时序一致性得分: 0-30 分 (节奏 + 平滑度)
    - 对称性得分: 0-30 分 (左右平衡)

    时序平滑: EMA 平滑角度序列 + EMA 平滑各子项得分，减少单帧波动.
    相位感知: 使用 PoseAnalyzer 传入的实际相位选择目标角度，避免自推断偏差.
    """

    def __init__(self, exercise_name: str, smooth_alpha: float = 0.7):
        self.exercise_name = exercise_name
        self.standard = EXERCISE_STANDARDS.get(exercise_name)
        self.smooth_alpha = smooth_alpha  # EMA 平滑系数
        self._angle_samples: list = []       # 原始角度值
        self._smoothed_angles: list = []     # EMA 平滑后角度值
        self._symmetry_diffs: dict[str, list] = {}  # 每帧各关节左右差值
        self._current_phase: str = "高位"     # 从 PoseAnalyzer 传入的实际相位

        # EMA 平滑后的得分缓存 (None = 尚未初始化)
        self._smooth_angle_score: Optional[float] = None
        self._smooth_temporal_score: Optional[float] = None
        self._smooth_symmetry_score: Optional[float] = None

    def update_angle(self, angle_value: Optional[float], phase: str):
        """记录一帧的角度（应用 EMA 平滑，存储相位用于目标选择）."""
        if angle_value is not None and phase != "等待":
            self._angle_samples.append(float(angle_value))
            self._current_phase = phase
            # EMA 平滑: smoothed = α * raw + (1-α) * prev_smoothed
            prev = self._smoothed_angles[-1] if self._smoothed_angles else float(angle_value)
            smoothed = self.smooth_alpha * float(angle_value) + (1 - self.smooth_alpha) * prev
            self._smoothed_angles.append(smoothed)

    def update_symmetry(self, angles: JointAngles):
        """记录一帧的对称性数据."""
        if self.standard is None:
            return
        for joint in self.standard.symmetry_joints:
            diff = angles.diff_symmetric(joint)
            if diff is not None:
                if joint not in self._symmetry_diffs:
                    self._symmetry_diffs[joint] = []
                self._symmetry_diffs[joint].append(diff)

    def compute(self, temporal: TemporalFeatures) -> ScoreResult:
        """计算最终评分 (含帧间 EMA 平滑，减少单帧误差)."""
        angle_score = self._score_angle()
        temporal_score = self._score_temporal(temporal)
        symmetry_score = self._score_symmetry()

        # EMA 平滑各子项得分，避免帧间剧烈跳动
        alpha = 0.6  # 得分平滑系数
        if self._smooth_angle_score is None:
            self._smooth_angle_score = angle_score
            self._smooth_temporal_score = temporal_score
            self._smooth_symmetry_score = symmetry_score
        else:
            self._smooth_angle_score = alpha * angle_score + (1 - alpha) * self._smooth_angle_score
            self._smooth_temporal_score = alpha * temporal_score + (1 - alpha) * self._smooth_temporal_score
            self._smooth_symmetry_score = alpha * symmetry_score + (1 - alpha) * self._smooth_symmetry_score

        total = self._smooth_angle_score + self._smooth_temporal_score + self._smooth_symmetry_score
        return ScoreResult(
            total=round(min(total, 100.0), 1),
            angle_score=round(self._smooth_angle_score, 1),
            temporal_score=round(self._smooth_temporal_score, 1),
            symmetry_score=round(self._smooth_symmetry_score, 1),
        )

    def _score_angle(self) -> float:
        """关节角度得分 (0-40).

        高斯衰减: score = 40 * exp(-(mean_dev/tolerance)²)
        使用 PoseAnalyzer 传入的实际相位选择目标角度，EMA 平滑抗噪声.
        """
        if not self.standard or not self._smoothed_angles:
            return 0.0

        # 根据实际相位选择目标角度
        if self._current_phase in ("低位", "保持"):
            target = self.standard.target_low
        else:
            target = self.standard.target_high

        tolerance = 10.0  # 容差 (度)

        # 取最近平滑样本 (~1秒)
        recent = self._smoothed_angles[-30:]

        deviations = [abs(a - target) for a in recent]
        mean_dev = float(np.mean(deviations))

        return 40.0 * math.exp(-((mean_dev / tolerance) ** 2))

    def _score_temporal(self, temporal: TemporalFeatures) -> float:
        """时序一致性得分 (0-30).

        - 节奏稳定性: 15分, CV < 15% 得满分. CV=0 且无 rep 数据时不给满分.
        - 动作平滑度: 15分, jerk 线性映射.
        """
        # CV=0 可能是无数据, 取不低于 0.03 避免未运动就得满分
        effective_cv = max(temporal.rhythm_consistency, 0.03)
        rhythm_score = 15.0 * max(0.0, 1.0 - effective_cv / 0.20)
        smooth_score = 15.0 * max(0.0, 1.0 - temporal.smoothness / 50.0)
        return rhythm_score + smooth_score

    def _score_symmetry(self) -> float:
        """对称性得分 (0-30).

        每个关注关节: 左右差异 < max_diff 得满分, 线性衰减.
        无数据时返回中性分 15，不盲目给满分.
        """
        if not self.standard or not self._symmetry_diffs:
            return 15.0  # 无数据返回中性分

        scores = []
        for joint in self.standard.symmetry_joints:
            diffs = self._symmetry_diffs.get(joint, [])
            if not diffs:
                scores.append(1.0)
                continue
            mean_diff = float(np.mean(diffs))
            max_allowed = self.standard.symmetry_max_diff
            # 线性衰减: diff=0 → 1.0, diff=max_allowed → 0.0
            joint_score = max(0.0, 1.0 - mean_diff / max_allowed)
            scores.append(joint_score)

        return 30.0 * float(np.mean(scores))

    def reset(self):
        self._angle_samples.clear()
        self._smoothed_angles.clear()
        self._symmetry_diffs.clear()
        self._smooth_angle_score = None
        self._smooth_temporal_score = None
        self._smooth_symmetry_score = None
        self._current_phase = "高位"


# ============================================================================
# 5. 常见错误动作识别
# ============================================================================

class ErrorDetector:
    """五类常见错误动作检测器."""

    # 连续帧阈值: 避免误报
    CONSECUTIVE_FRAMES = 5

    def __init__(self):
        self._error_counter: dict[str, int] = {}  # 错误名 → 连续帧计数

    def detect(self, angles: JointAngles, keypoints: np.ndarray,
               confidences: Optional[np.ndarray], phase: str,
               exercise: str) -> list[ErrorInfo]:
        """检测所有适用错误, 返回当前活跃的错误列表."""
        errors = []
        methods = {
            "深蹲":     [self._detect_knee_valgus, self._detect_back_rounding],
            "俯卧撑":   [self._detect_hip_sagging_pushup, self._detect_elbow_flare],
            "平板支撑": [self._detect_hip_sagging_plank],
            "卷腹":     [self._detect_neck_strain],
            "开合跳":   [self._detect_incomplete_spread],
            "引体向上": [self._detect_pullup_swing, self._detect_elbow_flare],
            "臀桥":     [self._detect_bridge_asymmetry, self._detect_hip_sagging_pushup],
            "高抬腿":   [self._detect_high_knee_lean, self._detect_knee_valgus],
            "肩推":     [self._detect_shoulder_press_arch, self._detect_elbow_flare],
            "侧平举":   [self._detect_lateral_raise_swing, self._detect_elbow_flare],
        }

        for detector in methods.get(exercise, []):
            error = detector(angles, keypoints, confidences, phase)
            if error:
                self._error_counter[error.name] = self._error_counter.get(error.name, 0) + 1
                if self._error_counter[error.name] >= self.CONSECUTIVE_FRAMES:
                    errors.append(error)
            else:
                self._error_counter.pop(detector.__name__, None)

        return errors

    # --- 错误 1: 深蹲膝盖内扣 ---
    def _detect_knee_valgus(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """膝关节水平偏移超过踝间距 15% 判定为膝盖内扣."""
        if phase != "低位":
            return None
        for side, ids in [("left", (11, 13, 15)), ("right", (12, 14, 16))]:
            hip_i, knee_i, ankle_i = ids
            if not all(valid_point(kp, conf, i) for i in ids):
                continue
            ankle_dist = point_distance(kp[ankle_i], kp[hip_i])
            # 膝的水平偏移 (相对髋-踝连线中点)
            knee_offset = point_to_line_distance(kp[knee_i], kp[hip_i], kp[ankle_i])
            if ankle_dist > 1 and knee_offset / ankle_dist > 0.15:
                side_cn = "左膝" if side == "left" else "右膝"
                return ErrorInfo(
                    name="膝盖内扣",
                    severity=2,
                    message=f"检测到{side_cn}内扣",
                    suggestion="保持膝盖与脚尖方向一致，有意识地将膝盖向外打开",
                )
        return None

    # --- 错误 2: 俯卧撑塌腰 ---
    def _detect_hip_sagging_pushup(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """髋点偏离肩-踝连线超过体长 8%."""
        if phase != "低位":
            return None
        return self._check_hip_sag(kp, conf, ratio=0.08, name="俯卧撑塌腰",
                                   suggestion="收紧核心和臀部，保持身体呈一条直线")

    # --- 错误 3: 深蹲弓背 ---
    def _detect_back_rounding(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """躯干前倾角 > 45°."""
        if phase != "低位":
            return None
        if angles.trunk_angle is not None and angles.trunk_angle > 45.0:
            return ErrorInfo(
                name="深蹲弓背",
                severity=2,
                message=f"躯干前倾 {angles.trunk_angle:.0f}°，疑似弓背",
                suggestion="挺胸收腹，保持背部直立，目视前方",
            )
        return None

    # --- 错误 4: 平板支撑塌腰 ---
    def _detect_hip_sagging_plank(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """髋点偏离肩-踝连线超过体长 6%."""
        return self._check_hip_sag(kp, conf, ratio=0.06, name="平板支撑塌腰",
                                   suggestion="收紧腹部和臀部，避免髋部下垂或上抬")

    # --- 错误 5: 卷腹颈部用力 ---
    def _detect_neck_strain(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """鼻-肩距离变化与躯干角变化比率 > 0.5，说明过度收下巴."""
        if phase != "低位":
            return None
        # 检查鼻(0)到左肩(5)和右肩(6)中点距离 vs 躯干角
        if valid_point(kp, conf, 0) and valid_point(kp, conf, 5) and valid_point(kp, conf, 6):
            shoulder_mid = (kp[5] + kp[6]) / 2
            nose_to_shoulder = point_distance(kp[0], shoulder_mid)
            # 经验阈值: 正常卷腹鼻-肩距离变化有限
            if nose_to_shoulder < 15.0:  # 像素阈值, 太近说明收下巴
                return ErrorInfo(
                    name="卷腹颈部用力",
                    severity=1,
                    message="检测到颈部过度用力",
                    suggestion="双手轻扶耳侧，下巴微收保持一拳距离，用腹部发力而非颈部",
                )
        return None

    # --- 辅助错误: 俯卧撑肘部过度外展 ---
    def _detect_elbow_flare(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """肩关节角度 > 120° 或 < 50° 表示肘部位置不当."""
        if phase != "低位":
            return None
        sh_l = angles.shoulder_left
        sh_r = angles.shoulder_right
        if sh_l is not None and (sh_l > 120.0 or sh_l < 50.0):
            return ErrorInfo(
                name="肘部外展",
                severity=1,
                message="检测到肘部位置不当",
                suggestion="肘部与身体保持约45°夹角，避免过度外展",
            )
        if sh_r is not None and (sh_r > 120.0 or sh_r < 50.0):
            return ErrorInfo(
                name="肘部外展",
                severity=1,
                message="检测到肘部位置不当",
                suggestion="肘部与身体保持约45°夹角，避免过度外展",
            )
        return None

    # --- 辅助错误: 开合跳不完整 ---
    def _detect_incomplete_spread(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """检测开合跳时手脚是否充分展开."""
        if phase != "高位":
            return None
        # 检查手腕是否过肩
        if valid_point(kp, conf, 9) and valid_point(kp, conf, 5):
            if kp[9][1] > kp[5][1]:  # 手腕在肩下方
                return ErrorInfo(
                    name="手臂未充分展开",
                    severity=1,
                    message="开合跳时手臂未举过头顶",
                    suggestion="跳起时手臂充分向上伸展过头顶",
                )
        return None

    def _check_hip_sag(self, kp, conf, ratio: float,
                       name: str, suggestion: str) -> Optional[ErrorInfo]:
        """通用髋部下塌检测."""
        required = [5, 6, 11, 12, 15, 16]
        if not all(valid_point(kp, conf, i) for i in required):
            return None
        shoulder_mid = (kp[5] + kp[6]) / 2
        hip_mid = (kp[11] + kp[12]) / 2
        ankle_mid = (kp[15] + kp[16]) / 2
        body_length = point_distance(shoulder_mid, ankle_mid)
        if body_length < 1:
            return None
        hip_deviation = point_to_line_distance(hip_mid, shoulder_mid, ankle_mid)
        if hip_deviation / body_length > ratio:
            return ErrorInfo(name=name, severity=2,
                             message=f"检测到髋部下塌 (偏离 {hip_deviation/body_length*100:.0f}%)",
                             suggestion=suggestion)
        return None

    # --- 辅助错误: 侧平举身体晃动 ---
    def _detect_lateral_raise_swing(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """侧平举时躯干倾角 > 15° 表示身体借力晃动."""
        if phase != "高位":
            return None
        if angles.trunk_angle is not None and angles.trunk_angle > 15.0:
            return ErrorInfo(
                name="身体晃动借力",
                severity=1,
                message=f"躯干倾斜 {angles.trunk_angle:.0f}°，疑似借力",
                suggestion="保持躯干稳定直立，仅用肩部发力完成侧平举",
            )
        return None

    # --- 辅助错误: 引体向上摆动 ---
    def _detect_pullup_swing(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """引体向上时躯干倾角 > 12° 表示身体摆动借力."""
        if angles.trunk_angle is not None and angles.trunk_angle > 12.0:
            return ErrorInfo(
                name="身体摆动",
                severity=2,
                message=f"躯干倾斜 {angles.trunk_angle:.0f}°，疑似摆动借力",
                suggestion="收紧核心，控制身体稳定，避免借助惯性摆动",
            )
        return None

    # --- 辅助错误: 臀桥不对称 ---
    def _detect_bridge_asymmetry(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """臀桥高位时左右髋角差异 > 10° 表示发力不对称."""
        if phase != "高位":
            return None
        hip_l = angles.hip_left
        hip_r = angles.hip_right
        if hip_l is not None and hip_r is not None:
            diff = abs(hip_l - hip_r)
            if diff > 10.0:
                return ErrorInfo(
                    name="臀桥不对称",
                    severity=1,
                    message=f"左右髋角相差 {diff:.0f}°",
                    suggestion="均匀发力，确保双侧臀部同时抬起",
                )
        return None

    # --- 辅助错误: 高抬腿身体后仰 ---
    def _detect_high_knee_lean(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """高抬腿时躯干倾角 > 18° 表示身体后仰."""
        if angles.trunk_angle is not None and angles.trunk_angle > 18.0:
            return ErrorInfo(
                name="身体后仰",
                severity=2,
                message=f"躯干倾斜 {angles.trunk_angle:.0f}°，疑似后仰",
                suggestion="保持上身挺直微前倾，核心收紧，目视前方",
            )
        return None

    # --- 辅助错误: 肩推弓背 ---
    def _detect_shoulder_press_arch(self, angles: JointAngles, kp, conf, phase) -> Optional[ErrorInfo]:
        """肩推时躯干倾角 > 15° 表示过度弓背."""
        if angles.trunk_angle is not None and angles.trunk_angle > 15.0:
            return ErrorInfo(
                name="肩推弓背",
                severity=2,
                message=f"躯干倾斜 {angles.trunk_angle:.0f}°，疑似弓背借力",
                suggestion="收紧核心，保持背部直立，避免过度后仰借力",
            )
        return None

    def reset(self):
        self._error_counter.clear()


# ============================================================================
# 6. PoseAnalyzer 主类
# ============================================================================

class PoseAnalyzer:
    """姿态分析器 — 对外统一接口.

    用法:
        analyzer = PoseAnalyzer("深蹲")
        result = analyzer.analyze_frame(keypoints, confidences)
        score = analyzer.get_score()
        errors = analyzer.get_errors()
    """

    def __init__(self, exercise_name: str):
        if exercise_name not in EXERCISE_STANDARDS:
            raise ValueError(f"不支持的动作: {exercise_name}. "
                             f"支持: {list(EXERCISE_STANDARDS.keys())}")
        self.exercise_name = exercise_name
        self.standard = EXERCISE_STANDARDS[exercise_name]

        self._angle_extractor = JointAngleExtractor()
        self._temporal_extractor = TemporalFeatureExtractor()
        self._scorer = MovementScorer(exercise_name)
        self._error_detector = ErrorDetector()

        # 计数状态机
        self.count = 0
        self.phase = "等待"
        self._hold_start: Optional[float] = None
        self.hold_time = 0.0

    def analyze_frame(self, keypoints: np.ndarray,
                      confidences: Optional[np.ndarray] = None) -> AnalysisResult:
        """处理一帧关键点数据, 返回完整分析结果."""
        # 1. 提取关节角度
        angles = self._angle_extractor.extract(keypoints, confidences)

        # 2. 获取主角度值
        primary_val = angles.primary_angle(self.exercise_name)

        # 3. 相位检测与计数
        self._update_phase_and_count(angles, primary_val)

        # 4. 时序特征
        temporal = self._temporal_extractor.update(primary_val, self.phase)

        # 5. 错误检测
        errors = self._error_detector.detect(angles, keypoints, confidences,
                                              self.phase, self.exercise_name)

        # 6. 评分更新
        self._scorer.update_angle(primary_val, self.phase)
        self._scorer.update_symmetry(angles)
        score = self._scorer.compute(temporal)

        return AnalysisResult(
            angles=angles,
            temporal=temporal,
            phase=self.phase,
            count=self.count,
            hold_time=self.hold_time,
            errors=errors,
            score=score,
        )

    def _update_phase_and_count(self, angles: JointAngles,
                                 primary_val: Optional[float]):
        """运动相位状态机 + 计数."""
        std = self.standard
        low_min, low_max = std.low_range
        high_min, high_max = std.high_range

        if primary_val is None:
            return

        if std.hold_threshold is not None:
            # 平板支撑等静态动作: 计时
            if low_min <= primary_val <= low_max:
                if self._hold_start is None:
                    self._hold_start = time.time()
                    self.phase = "保持"
                else:
                    self.hold_time = time.time() - self._hold_start
                    self.phase = "保持"
            else:
                self._hold_start = None
                self.phase = "姿态调整"
            return

        # 动态动作计数
        if std.count_trigger == "high":
            if primary_val <= low_max:
                self.phase = "低位"
            elif primary_val >= high_min and self.phase == "低位":
                self.count += 1
                self.phase = "高位"
            elif primary_val >= high_min and self.phase == "等待":
                self.phase = "高位"
        else:
            if primary_val >= high_min:
                self.phase = "高位"
            elif primary_val <= low_max and self.phase == "高位":
                self.count += 1
                self.phase = "低位"
            elif primary_val <= low_max and self.phase == "等待":
                self.phase = "低位"

    def get_score(self) -> ScoreResult:
        return self._scorer.compute(self._temporal_extractor.update(None, self.phase))

    def get_errors(self) -> list[ErrorInfo]:
        """获取当前活跃错误（简化版，不传关键点则返回空）."""
        return []

    def reset(self):
        self.count = 0
        self.phase = "等待"
        self._hold_start = None
        self.hold_time = 0.0
        self._temporal_extractor.reset()
        self._scorer.reset()
        self._error_detector.reset()


# ============================================================================
# 自测代码
# ============================================================================

def _self_test():
    """模块自测: 用合成关键点验证各组件计算正确性."""
    print("=" * 60)
    print("pose_analyzer 自测")
    print("=" * 60)

    # 合成一帧标准站姿关键点 (17, 2), 模拟身高约 170cm 在 640x480 图像上
    kp = np.array([
        [320, 80],   # 0  nose
        [305, 70],   # 1  left_eye
        [335, 70],   # 2  right_eye
        [295, 75],   # 3  left_ear
        [345, 75],   # 4  right_ear
        [280, 140],  # 5  left_shoulder
        [360, 140],  # 6  right_shoulder
        [240, 220],  # 7  left_elbow
        [400, 220],  # 8  right_elbow
        [210, 300],  # 9  left_wrist
        [430, 300],  # 10 right_wrist
        [290, 280],  # 11 left_hip
        [350, 280],  # 12 right_hip
        [280, 380],  # 13 left_knee
        [360, 380],  # 14 right_knee
        [275, 470],  # 15 left_ankle
        [365, 470],  # 16 right_ankle
    ], dtype=np.float32)
    conf = np.ones(17, dtype=np.float32) * 0.9

    # --- 测试 1: 关节角度提取 ---
    print("\n[1] 关节角度提取")
    extractor = JointAngleExtractor()
    angles = extractor.extract(kp, conf)
    print(f"  左膝角度: {angles.knee_left:.1f}°")
    print(f"  右膝角度: {angles.knee_right:.1f}°")
    print(f"  左肘角度: {angles.elbow_left:.1f}°")
    print(f"  右肘角度: {angles.elbow_right:.1f}°")
    print(f"  左髋角度: {angles.hip_left:.1f}°")
    print(f"  右髋角度: {angles.hip_right:.1f}°")
    print(f"  躯干倾角: {angles.trunk_angle:.1f}°")

    # 站姿应接近 180° 膝角
    assert angles.knee_left is not None and angles.knee_left > 150, f"站姿膝角应 >150°, 实际 {angles.knee_left:.1f}"
    assert angles.knee_right is not None and angles.knee_right > 150, f"站姿膝角应 >150°, 实际 {angles.knee_right:.1f}"
    print("  [PASS] 站姿膝角验证通过")

    # --- 测试 2: 时序特征 ---
    print("\n[2] 时序特征提取")
    temporal_ext = TemporalFeatureExtractor(window_size=30)
    # 模拟 10 帧稳定角度
    for _ in range(10):
        features = temporal_ext.update(170.0, "高位")
    print(f"  角速度: {features.angular_velocity:.2f} °/s")
    print(f"  平滑度: {features.smoothness:.2f}")
    assert features.angular_velocity < 1.0, f"稳定帧角速度应接近0, 实际 {features.angular_velocity:.2f}"
    print("  [PASS] 稳定时序验证通过")

    # --- 测试 3: 动作标准参数 ---
    print("\n[3] 动作标准参数")
    all_exercises = ["深蹲", "俯卧撑", "平板支撑", "卷腹", "开合跳",
                     "引体向上", "臀桥", "高抬腿", "肩推", "侧平举"]
    for name in all_exercises:
        std = EXERCISE_STANDARDS.get(name)
        assert std is not None, f"缺少动作: {name}"
        print(f"  {name}: 主关节={std.primary_joint}, "
              f"低位={std.low_range}, 高位={std.high_range}")
    print(f"  [PASS] 全部{len(all_exercises)}个动作已定义")

    # --- 测试 4: 评分算法 ---
    print("\n[4] 评分算法")
    scorer = MovementScorer("深蹲")
    # 模拟完美的深蹲角度: 170° 高位保持
    for _ in range(20):
        scorer.update_angle(170.0, "高位")
        scorer.update_symmetry(angles)
    temporal = TemporalFeatures(angular_velocity=5.0, smoothness=2.0,
                                 rhythm_consistency=0.05, rom_consistency=0.03)
    score = scorer.compute(temporal)
    print(f"  总分: {score.total:.1f}/100")
    print(f"  角度得分: {score.angle_score:.1f}/40")
    print(f"  时序得分: {score.temporal_score:.1f}/30")
    print(f"  对称得分: {score.symmetry_score:.1f}/30")
    assert score.total > 70, f"完美动作得分应 >70, 实际 {score.total:.1f}"
    print("  [PASS] 评分验证通过")

    # --- 测试 5: 错误检测 ---
    print("\n[5] 错误检测")

    # 5a: 深蹲膝盖内扣 — 构造膝部内扣的关键点
    kp_valgus = kp.copy()
    kp_valgus[13] = [265, 380]  # 左膝向内偏移
    kp_valgus[14] = [375, 380]  # 右膝向内偏移
    detector = ErrorDetector()
    angles_bad = extractor.extract(kp_valgus, conf)
    errors = detector.detect(angles_bad, kp_valgus, conf, "低位", "深蹲")
    # 连续调用 5 次以上触发
    for _ in range(6):
        errors = detector.detect(angles_bad, kp_valgus, conf, "低位", "深蹲")
    knee_valgus_errors = [e for e in errors if e.name == "膝盖内扣"]
    if knee_valgus_errors:
        print(f"  [PASS] 深蹲膝盖内扣: 已检测 — {knee_valgus_errors[0].suggestion}")
    else:
        print("  [WARN] 深蹲膝盖内扣: 未触发 (阈值可能需要调整)")

    # 5b: 深蹲弓背 — 躯干倾角异常
    kp_round = kp.copy()
    kp_round[5] = [310, 160]   # 肩前移
    kp_round[6] = [390, 160]
    kp_round[11] = [320, 280]  # 髋前移
    kp_round[12] = [380, 280]
    angles_round = extractor.extract(kp_round, conf)
    detector2 = ErrorDetector()
    for _ in range(6):
        errors = detector2.detect(angles_round, kp_round, conf, "低位", "深蹲")
    back_errors = [e for e in errors if e.name == "深蹲弓背"]
    if back_errors:
        print(f"  [PASS] 深蹲弓背: 已检测 — {back_errors[0].suggestion}")
    else:
        print(f"  [WARN] 深蹲弓背: 未触发 (躯干角={angles_round.trunk_angle:.1f}°)")

    # 5c: 俯卧撑塌腰 — 构造塌腰关键点
    kp_sag = np.array([
        [320, 70],   # 0  nose
        [310, 60],   # 1
        [330, 60],   # 2
        [300, 65],   # 3
        [340, 65],   # 4
        [280, 150],  # 5  shoulder
        [360, 150],  # 6
        [250, 220],  # 7  elbow
        [390, 220],  # 8
        [220, 190],  # 9  wrist
        [420, 190],  # 10
        [290, 300],  # 11 hip (偏低)
        [350, 300],  # 12 hip
        [285, 380],  # 13 knee
        [355, 380],  # 14 knee
        [280, 460],  # 15 ankle
        [360, 460],  # 16 ankle
    ], dtype=np.float32)
    angles_sag = extractor.extract(kp_sag, conf)
    detector3 = ErrorDetector()
    for _ in range(6):
        errors = detector3.detect(angles_sag, kp_sag, conf, "低位", "俯卧撑")
    sag_errors = [e for e in errors if "塌腰" in e.name]
    if sag_errors:
        print(f"  [PASS] 俯卧撑塌腰: 已检测 — {sag_errors[0].suggestion}")
    else:
        print("  [WARN] 俯卧撑塌腰: 未触发 (阈值可能需要调整)")

    # 5d: 卷腹颈部用力
    kp_neck = kp.copy()
    kp_neck[0] = [320, 100]  # 鼻子离肩太近
    angles_neck = extractor.extract(kp_neck, conf)
    # 调整躯干角模拟卷腹
    angles_neck.trunk_angle = 40.0
    detector4 = ErrorDetector()
    for _ in range(6):
        errors = detector4.detect(angles_neck, kp_neck, conf, "低位", "卷腹")
    neck_errors = [e for e in errors if e.name == "卷腹颈部用力"]
    if neck_errors:
        print(f"  [PASS] 卷腹颈部用力: 已检测 — {neck_errors[0].suggestion}")
    else:
        print("  [WARN] 卷腹颈部用力: 未触发 (阈值可能需要调整)")

    print("\n" + "=" * 60)
    print("自测完成")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
