"""
User profile dataclass with JSON file persistence.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

DEFAULT_PROFILE_DIR = Path("./user_profiles")


class FitnessLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class FitnessGoal(Enum):
    STRENGTH = "strength"       # 增肌力量
    HYPERTROPHY = "hypertrophy"  # 肌肉线条
    ENDURANCE = "endurance"      # 耐力
    WEIGHT_LOSS = "weight_loss"  # 减脂
    GENERAL = "general"          # 综合健康


class Equipment(Enum):
    NONE = "none"
    MAT = "mat"
    DUMBBELLS = "dumbbells"
    RESISTANCE_BAND = "band"
    FULL_GYM = "full_gym"


@dataclass
class ExerciseRecord:
    """History record for a single exercise."""
    best_count: int = 0
    best_score: float = 0.0
    total_sessions: int = 0
    total_reps: int = 0
    last_date: Optional[str] = None
    last_score: float = 0.0

    def update(self, reps: int, score: float):
        self.total_sessions += 1
        self.total_reps += reps
        self.last_date = datetime.now().isoformat()[:10]
        self.last_score = score
        if reps > self.best_count:
            self.best_count = reps
        if score > self.best_score:
            self.best_score = score


@dataclass
class UserProfile:
    """User profile with fitness data and exercise history."""
    name: str = "用户"
    age: int = 25
    weight_kg: float = 70.0
    height_cm: float = 170.0
    fitness_level: FitnessLevel = FitnessLevel.BEGINNER
    goal: FitnessGoal = FitnessGoal.GENERAL
    equipment: Equipment = Equipment.MAT
    injury_history: str = ""
    liked_exercises: list[str] = field(default_factory=list)
    disliked_exercises: list[str] = field(default_factory=list)
    training_days_per_week: int = 3
    pain_points: list[dict] = field(default_factory=list)
    workout_history: list[dict] = field(default_factory=list)
    medical_notes: str = ""
    exercise_history: dict[str, ExerciseRecord] = field(default_factory=dict)
    created_date: str = field(default_factory=lambda: datetime.now().isoformat()[:10])

    def get_exercise_record(self, exercise_name: str) -> ExerciseRecord:
        if exercise_name not in self.exercise_history:
            self.exercise_history[exercise_name] = ExerciseRecord()
        return self.exercise_history[exercise_name]

    def update_after_session(self, exercise_name: str, reps: int, score: float):
        record = self.get_exercise_record(exercise_name)
        record.update(reps, score)

    def to_dict(self) -> dict:
        result = {}
        result["name"] = self.name
        result["age"] = self.age
        result["weight_kg"] = self.weight_kg
        result["height_cm"] = self.height_cm
        result["fitness_level"] = self.fitness_level.value
        result["goal"] = self.goal.value
        result["equipment"] = self.equipment.value
        result["injury_history"] = self.injury_history
        result["liked_exercises"] = self.liked_exercises
        result["disliked_exercises"] = self.disliked_exercises
        result["training_days_per_week"] = self.training_days_per_week
        result["pain_points"] = self.pain_points
        result["workout_history"] = self.workout_history
        result["medical_notes"] = self.medical_notes
        result["exercise_history"] = {
            k: asdict(v) for k, v in self.exercise_history.items()
        }
        result["created_date"] = self.created_date
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        data = dict(data)
        if isinstance(data.get("fitness_level"), str):
            data["fitness_level"] = FitnessLevel(data["fitness_level"])
        if isinstance(data.get("goal"), str):
            data["goal"] = FitnessGoal(data["goal"])
        if isinstance(data.get("equipment"), str):
            data["equipment"] = Equipment(data["equipment"])
        history = {}
        for k, v in data.get("exercise_history", {}).items():
            history[k] = ExerciseRecord(**v)
        data["exercise_history"] = history
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in field_names})

    def save(self, profile_dir: Path = DEFAULT_PROFILE_DIR) -> Path:
        profile_dir.mkdir(parents=True, exist_ok=True)
        path = profile_dir / f"{self.name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, name: str, profile_dir: Path = DEFAULT_PROFILE_DIR) -> "UserProfile":
        path = profile_dir / f"{name}.json"
        if not path.exists():
            return cls(name=name)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
