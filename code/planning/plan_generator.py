"""
Personalized workout plan generation algorithm.

Rule-based system with progressive overload.
Generates weekly plans based on user profile.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .user_profile import UserProfile, FitnessLevel, FitnessGoal, ExerciseRecord

DIFFICULTY_LEVELS = {
    "深蹲": {
        FitnessLevel.BEGINNER:     {"sets": 2, "reps": 10, "rest_s": 60},
        FitnessLevel.INTERMEDIATE: {"sets": 3, "reps": 15, "rest_s": 45},
        FitnessLevel.ADVANCED:     {"sets": 4, "reps": 20, "rest_s": 30},
    },
    "俯卧撑": {
        FitnessLevel.BEGINNER:     {"sets": 2, "reps": 8,  "rest_s": 60},
        FitnessLevel.INTERMEDIATE: {"sets": 3, "reps": 12, "rest_s": 45},
        FitnessLevel.ADVANCED:     {"sets": 4, "reps": 18, "rest_s": 30},
    },
    "平板支撑": {
        FitnessLevel.BEGINNER:     {"sets": 2, "reps": 20, "rest_s": 30},
        FitnessLevel.INTERMEDIATE: {"sets": 3, "reps": 45, "rest_s": 20},
        FitnessLevel.ADVANCED:     {"sets": 4, "reps": 60, "rest_s": 15},
    },
    "卷腹": {
        FitnessLevel.BEGINNER:     {"sets": 2, "reps": 10, "rest_s": 45},
        FitnessLevel.INTERMEDIATE: {"sets": 3, "reps": 15, "rest_s": 30},
        FitnessLevel.ADVANCED:     {"sets": 4, "reps": 25, "rest_s": 20},
    },
    "开合跳": {
        FitnessLevel.BEGINNER:     {"sets": 2, "reps": 15, "rest_s": 30},
        FitnessLevel.INTERMEDIATE: {"sets": 3, "reps": 25, "rest_s": 20},
        FitnessLevel.ADVANCED:     {"sets": 4, "reps": 35, "rest_s": 15},
    },
}

GOAL_WEIGHTS = {
    FitnessGoal.STRENGTH: {
        "深蹲": 0.30, "俯卧撑": 0.30, "平板支撑": 0.15,
        "卷腹": 0.10, "开合跳": 0.15,
    },
    FitnessGoal.HYPERTROPHY: {
        "深蹲": 0.25, "俯卧撑": 0.25, "平板支撑": 0.10,
        "卷腹": 0.20, "开合跳": 0.20,
    },
    FitnessGoal.ENDURANCE: {
        "深蹲": 0.20, "俯卧撑": 0.20, "平板支撑": 0.20,
        "卷腹": 0.20, "开合跳": 0.20,
    },
    FitnessGoal.WEIGHT_LOSS: {
        "深蹲": 0.20, "俯卧撑": 0.15, "平板支撑": 0.15,
        "卷腹": 0.15, "开合跳": 0.35,
    },
    FitnessGoal.GENERAL: {
        "深蹲": 0.25, "俯卧撑": 0.25, "平板支撑": 0.15,
        "卷腹": 0.15, "开合跳": 0.20,
    },
}

ALL_EXERCISES = ["深蹲", "俯卧撑", "平板支撑", "卷腹", "开合跳"]

EXERCISE_NOTES = {
    "深蹲": "保持背部挺直，膝盖与脚尖方向一致",
    "俯卧撑": "身体保持一条直线，核心收紧",
    "平板支撑": "保持身体呈一条直线，不要塌腰",
    "卷腹": "用腹部发力，不要用颈部",
    "开合跳": "手脚充分打开，落地轻盈",
}

DAY_NOTES = {
    "下肢": "训练前做好髋膝踝热身",
    "上肢": "注意肩关节活动度热身",
    "核心": "控制呼吸，每个动作顶峰收缩",
    "全身": "组间休息充分，保持心率适中",
    "有氧": "保持心率在燃脂区间",
}


@dataclass
class ExercisePlan:
    name: str
    sets: int
    reps: int
    rest_seconds: int
    notes: str = ""


@dataclass
class DailyPlan:
    day: str
    focus: str
    exercises: list[ExercisePlan] = field(default_factory=list)
    notes: str = ""


@dataclass
class WeeklyWorkoutPlan:
    user_name: str
    goal: str
    level: str
    week_start: str
    days: list[DailyPlan] = field(default_factory=list)
    notes: str = ""

    def to_text(self) -> str:
        """Format as readable Chinese text."""
        lines = [
            f"📋 {self.user_name} 的周训练计划",
            f"目标: {self.goal} | 水平: {self.level}",
            f"起始: {self.week_start}",
            "=" * 40,
        ]
        for day in self.days:
            lines.append(f"\n📅 {day.day} ({day.focus})")
            for ex in day.exercises:
                unit = "秒" if ex.name == "平板支撑" else "次"
                lines.append(
                    f"  • {ex.name}: {ex.sets}组×{ex.reps}{unit}, "
                    f"组间休息{ex.rest_seconds}秒"
                )
                if ex.notes:
                    lines.append(f"    ↳ {ex.notes}")
            if day.notes:
                lines.append(f"  备注: {day.notes}")
        lines.append(f"\n📌 总体备注:\n{self.notes}")
        return "\n".join(lines)


class PlanGenerator:
    """Generate personalized workout plans based on user profile."""

    def __init__(self, profile: UserProfile):
        self.profile = profile

    def generate_weekly_plan(self) -> WeeklyWorkoutPlan:
        """Generate a weekly workout plan."""
        profile = self.profile

        days_per_week = {
            FitnessLevel.BEGINNER: 3,
            FitnessLevel.INTERMEDIATE: 4,
            FitnessLevel.ADVANCED: 5,
        }
        n_days = days_per_week[profile.fitness_level]

        day_configs = self._get_day_configs(n_days)

        daily_plans = []
        for day_name, focus in day_configs:
            exercises = self._select_exercises(focus)
            daily_plans.append(DailyPlan(
                day=day_name,
                focus=focus,
                exercises=exercises,
                notes=DAY_NOTES.get(focus, "充分热身，量力而行"),
            ))

        return WeeklyWorkoutPlan(
            user_name=profile.name,
            goal=self._goal_label(profile.goal),
            level=self._level_label(profile.fitness_level),
            week_start=datetime.now().isoformat()[:10],
            days=daily_plans,
            notes=self._overall_notes(),
        )

    def _get_day_configs(self, n_days: int) -> list[tuple[str, str]]:
        configs = {
            3: [("周一", "全身"), ("周三", "全身"), ("周五", "全身")],
            4: [("周一", "下肢"), ("周二", "上肢"), ("周四", "核心"),
                ("周五", "全身")],
            5: [("周一", "下肢"), ("周二", "上肢"), ("周三", "核心"),
                ("周五", "全身"), ("周六", "有氧")],
        }
        return configs.get(n_days, configs[3])

    def _select_exercises(self, focus: str) -> list[ExercisePlan]:
        profile = self.profile
        weights = GOAL_WEIGHTS.get(profile.goal, GOAL_WEIGHTS[FitnessGoal.GENERAL])

        focus_exercise_map = {
            "下肢": ["深蹲"],
            "上肢": ["俯卧撑"],
            "核心": ["平板支撑", "卷腹"],
            "全身": ["深蹲", "俯卧撑", "开合跳"],
            "有氧": ["开合跳", "深蹲"],
        }

        primary = focus_exercise_map.get(focus, ["深蹲", "俯卧撑"])
        selected = []

        for ex_name in primary:
            if ex_name in DIFFICULTY_LEVELS:
                ex_level = DIFFICULTY_LEVELS[ex_name].get(
                    profile.fitness_level,
                    DIFFICULTY_LEVELS[ex_name][FitnessLevel.BEGINNER],
                )
                selected.append(self._make_plan(ex_name, ex_level))

        # Fill to at least 2 exercises if needed
        while len(selected) < 2:
            candidates = [e for e in ALL_EXERCISES
                         if e not in [p.name for p in selected]]
            if not candidates:
                break
            ex_name = random.choices(
                candidates,
                weights=[weights.get(e, 0.2) for e in candidates],
                k=1,
            )[0]
            ex_level = DIFFICULTY_LEVELS[ex_name].get(
                profile.fitness_level,
                DIFFICULTY_LEVELS[ex_name][FitnessLevel.BEGINNER],
            )
            selected.append(self._make_plan(ex_name, ex_level))

        return selected

    def _make_plan(self, ex_name: str, level: dict) -> ExercisePlan:
        """Create an ExercisePlan with potential progressive overload."""
        record = self.profile.get_exercise_record(ex_name)
        sets = level["sets"]
        reps = level["reps"]

        if record.total_sessions >= 2 and record.best_count >= reps * sets:
            reps = int(reps * 1.1)

        return ExercisePlan(
            name=ex_name,
            sets=sets,
            reps=reps,
            rest_seconds=level["rest_s"],
            notes=EXERCISE_NOTES.get(ex_name, ""),
        )

    def _overall_notes(self) -> str:
        notes = (
            "1. 每次训练前热身5-10分钟\n"
            "2. 训练后拉伸5-10分钟\n"
            "3. 保持规律作息和充足睡眠\n"
            "4. 如有不适立即停止，咨询专业人士"
        )
        if self.profile.medical_notes:
            notes += f"\n5. ⚠ 注意事项: {self.profile.medical_notes}"
        return notes

    @staticmethod
    def _goal_label(goal: FitnessGoal) -> str:
        labels = {
            FitnessGoal.STRENGTH: "增肌力量",
            FitnessGoal.HYPERTROPHY: "肌肉线条",
            FitnessGoal.ENDURANCE: "耐力提升",
            FitnessGoal.WEIGHT_LOSS: "减脂塑形",
            FitnessGoal.GENERAL: "综合健康",
        }
        return labels.get(goal, "综合健康")

    @staticmethod
    def _level_label(level: FitnessLevel) -> str:
        labels = {
            FitnessLevel.BEGINNER: "初学者",
            FitnessLevel.INTERMEDIATE: "中级",
            FitnessLevel.ADVANCED: "高级",
        }
        return labels.get(level, "初学者")
