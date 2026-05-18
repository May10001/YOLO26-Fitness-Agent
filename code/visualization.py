"""
关节角度可视化对比模块
========================
提供标准动作与用户动作的关节角度热力图对比，
支持单帧对比和时序角度曲线。
"""

import math
from typing import Optional

import numpy as np

# 关节显示名称映射
JOINT_DISPLAY_NAMES = {
    "knee_left": "左膝", "knee_right": "右膝",
    "hip_left": "左髋", "hip_right": "右髋",
    "elbow_left": "左肘", "elbow_right": "右肘",
    "shoulder_left": "左肩", "shoulder_right": "右肩",
    "ankle_left": "左踝", "ankle_right": "右踝",
    "trunk": "躯干",
}

# 标准动作参考角度 (基于 EXERCISE_STANDARDS 的 target 值)
STANDARD_REFERENCE_ANGLES = {
    "深蹲":   {"knee": (75, 170), "hip": (70, 170), "trunk": (10, 35)},
    "俯卧撑": {"elbow": (75, 170), "shoulder": (50, 130), "trunk": (5, 20)},
    "平板支撑": {"elbow": (85, 95), "hip": (170, 180), "trunk": (0, 12)},
    "卷腹":   {"trunk": (5, 40), "hip": (80, 120), "knee": (60, 90)},
    "开合跳": {"elbow": (30, 170), "knee": (20, 170), "trunk": (0, 25)},
    "引体向上": {"elbow": (40, 170), "shoulder": (30, 170), "trunk": (0, 15)},
    "臀桥":   {"hip": (85, 175), "knee": (60, 140), "trunk": (0, 20)},
    "高抬腿": {"hip": (75, 170), "knee": (65, 170), "trunk": (0, 15)},
    "肩推":   {"elbow": (55, 170), "shoulder": (40, 170), "trunk": (0, 15)},
    "侧平举": {"shoulder": (5, 95), "elbow": (140, 175), "trunk": (0, 12)},
}


class JointAngleHeatmap:
    """标准动作与用户动作的关节角度可视化对比.

    生成两类图表:
    1. 热力图矩阵 — 每个关节的颜色代表偏离标准的程度 (绿→黄→红)
    2. 对比柱状图 — 标准角度 vs 用户角度 并排显示
    """

    def __init__(self, exercise_name: str):
        self.exercise_name = exercise_name
        self.reference = STANDARD_REFERENCE_ANGLES.get(exercise_name, {})
        self._user_samples: dict[str, list] = {}  # joint → [angles...]

    def record_frame(self, angles) -> None:
        """记录一帧的关节角度 (JointAngles 对象)."""
        mapping = {
            "knee_left": angles.knee_left, "knee_right": angles.knee_right,
            "hip_left": angles.hip_left, "hip_right": angles.hip_right,
            "elbow_left": angles.elbow_left, "elbow_right": angles.elbow_right,
            "shoulder_left": angles.shoulder_left, "shoulder_right": angles.shoulder_right,
            "ankle_left": angles.ankle_left, "ankle_right": angles.ankle_right,
            "trunk": angles.trunk_angle,
        }
        for name, value in mapping.items():
            if value is not None:
                if name not in self._user_samples:
                    self._user_samples[name] = []
                self._user_samples[name].append(value)

    def compute_deviation_matrix(self) -> dict:
        """计算各关节相对标准的偏离度矩阵.

        Returns:
            dict: {
                joint_name: {
                    "user_avg": float,
                    "standard_mid": float,
                    "deviation": float,     # 绝对偏离 (°)
                    "severity": str,         # "good"|"warning"|"bad"
                    "deviation_ratio": float, # 0~1 归一化偏离比
                }
            }
        """
        result = {}
        for joint_key, (low, high) in self.reference.items():
            standard_mid = (low + high) / 2
            standard_range = high - low

            for side in ["_left", "_right"] if joint_key != "trunk" else [""]:
                full_key = joint_key + side
                samples = self._user_samples.get(full_key, [])
                if not samples:
                    continue

                user_avg = float(np.mean(samples))
                deviation = abs(user_avg - standard_mid)

                # 偏离比: 实际偏离 / 标准范围的一半
                half_range = max(standard_range / 2, 1.0)
                deviation_ratio = min(deviation / half_range, 1.0)

                if deviation_ratio < 0.3:
                    severity = "good"
                elif deviation_ratio < 0.7:
                    severity = "warning"
                else:
                    severity = "bad"

                result[full_key] = {
                    "user_avg": round(user_avg, 1),
                    "standard_mid": round(standard_mid, 1),
                    "standard_range": (low, high),
                    "deviation": round(deviation, 1),
                    "deviation_ratio": round(deviation_ratio, 3),
                    "severity": severity,
                }
        return result

    def generate_heatmap_data(self) -> np.ndarray:
        """生成热力图数据矩阵.

        Returns:
            np.ndarray: (n_joints, 3) 矩阵 [user_avg, standard_mid, deviation]
        """
        matrix = self.compute_deviation_matrix()
        joints = sorted(matrix.keys(),
                       key=lambda k: ("" if "trunk" in k else
                                      ("0" if "left" in k else "1") + k))

        data = []
        labels = []
        for joint in joints:
            info = matrix[joint]
            data.append([info["user_avg"], info["standard_mid"], info["deviation"]])
            labels.append(JOINT_DISPLAY_NAMES.get(joint, joint))

        return np.array(data) if data else np.zeros((0, 3)), labels

    def get_summary(self) -> dict:
        """获取对比摘要."""
        matrix = self.compute_deviation_matrix()
        if not matrix:
            return {"overall_deviation": 0, "good_joints": 0,
                    "warning_joints": 0, "bad_joints": 0, "details": {}}

        deviations = [info["deviation"] for info in matrix.values()]
        severities = [info["severity"] for info in matrix.values()]

        return {
            "overall_deviation": round(float(np.mean(deviations)), 1),
            "max_deviation": round(float(np.max(deviations)), 1),
            "good_joints": severities.count("good"),
            "warning_joints": severities.count("warning"),
            "bad_joints": severities.count("bad"),
            "details": matrix,
        }

    def reset(self) -> None:
        self._user_samples.clear()


def generate_ascii_heatmap(deviation_matrix: dict, cols: int = 3) -> str:
    """生成 ASCII 文本热力图 (无需 matplotlib).

    用于终端环境快速查看对比结果.
    """
    if not deviation_matrix:
        return "(无数据)"

    blocks = {
        "good": "▓",    # 深色 = 接近标准
        "warning": "▒", # 中色 = 有偏差
        "bad": "░",     # 浅色 = 明显偏离
    }

    lines = []
    joints = list(deviation_matrix.keys())
    for i in range(0, len(joints), cols):
        row_joints = joints[i:i + cols]
        row_parts = []
        for joint in row_joints:
            info = deviation_matrix[joint]
            name = JOINT_DISPLAY_NAMES.get(joint, joint)
            bar = blocks[info["severity"]] * 5
            row_parts.append(f"{name:6s} {bar} {info['deviation']:5.1f}°")
        lines.append("  ".join(row_parts))

    lines.append(f"\n总关节数: {len(deviation_matrix)}")
    lines.append(f"标准 ▓  偏差 ▒  明显偏离 ░")
    return "\n".join(lines)


def _self_test():
    """模块自测."""
    print("=" * 60)
    print("visualization 自测")
    print("=" * 60)

    from code.pose_analyzer import JointAngles

    hm = JointAngleHeatmap("深蹲")

    # 模拟完美深蹲角度
    angles = JointAngles(
        knee_left=90, knee_right=92,
        hip_left=82, hip_right=80,
        trunk_angle=15,
    )
    for _ in range(20):
        hm.record_frame(angles)

    print("\n[1] 偏离矩阵 (完美深蹲):")
    matrix = hm.compute_deviation_matrix()
    for joint, info in matrix.items():
        print(f"  {JOINT_DISPLAY_NAMES.get(joint, joint)}: "
              f"用户={info['user_avg']}° 标准={info['standard_mid']}° "
              f"偏离={info['deviation']}° [{info['severity']}]")

    summary = hm.get_summary()
    print(f"\n[2] 摘要: 总偏离={summary['overall_deviation']}° "
          f"良好={summary['good_joints']} 警告={summary['warning_joints']} "
          f"差={summary['bad_joints']}")

    print("\n[3] ASCII 热力图:")
    print(generate_ascii_heatmap(matrix))

    print("\n" + "=" * 60)
    print("自测完成")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
