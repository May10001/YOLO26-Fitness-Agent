"""
Convert pipeline JSONL dataset to SFTTrainer-compatible chat messages format.

Input: data/processed/fitness_dataset.jsonl (1626 samples, mixed types)
Output: data/processed/training_data.jsonl (chat messages format)
        data/processed/eval_data.jsonl     (10% held-out for evaluation)

Usage:
    python -m code.models.fine_tuning.prepare_data
    python -m code.models.fine_tuning.prepare_data --input data/processed/fitness_dataset.jsonl
"""

import json
import logging
import random
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FITNESS_SYSTEM_PROMPT = (
    "你是一名专业的健身教练和运动科学顾问。你的职责是：\n"
    "1. 提供专业、安全的健身指导\n"
    "2. 纠正运动动作中的错误姿态\n"
    "3. 根据用户情况制定合理的训练计划\n"
    "4. 提供营养和恢复建议\n"
    "5. 强调安全第一，避免运动损伤\n\n"
    "请用中文回答，保持专业、鼓励、清晰的语气。回答应具体、可操作，"
    "避免模糊的建议。"
)

EXERCISE_LABELS = {
    "深蹲": "深蹲", "俯卧撑": "俯卧撑", "平板支撑": "平板支撑",
    "卷腹": "卷腹", "开合跳": "开合跳",
}

LEVEL_LABELS = {"beginner": "初学者", "intermediate": "中级", "advanced": "高级"}
GOAL_LABELS = {
    "strength": "增肌力量", "hypertrophy": "肌肉线条",
    "endurance": "耐力提升", "weight_loss": "减脂塑形", "general": "综合健康",
}
EQUIP_LABELS = {
    "none": "无器械（自重训练）", "mat": "瑜伽垫",
    "dumbbells": "哑铃", "resistance_band": "弹力带", "full_gym": "全器械",
}


def _build_correction_user_message(sample: dict) -> str:
    inp = sample.get("input", {})
    exercise = inp.get("exercise", sample.get("exercise", ""))
    error = inp.get("detected_error", sample.get("error", ""))
    severity = inp.get("severity", sample.get("severity", 2))
    trigger = inp.get("trigger", sample.get("trigger_condition", ""))

    sev_text = {1: "轻微", 2: "中等", 3: "严重"}.get(severity, "中等")
    parts = [
        f"我在做{exercise}时检测到{error}的问题（严重程度：{sev_text}）。",
        f"触发条件：{trigger}" if trigger else "",
        f"请帮我纠正这个动作错误，告诉我为什么会这样以及如何改善。",
    ]
    return " ".join(p for p in parts if p)


def _build_planning_user_message(sample: dict) -> str:
    inp = sample.get("input", {})
    age = inp.get("age", 25)
    weight = inp.get("weight_kg", 70)
    height = inp.get("height_cm", 170)
    gender = inp.get("gender", "男")
    level = LEVEL_LABELS.get(inp.get("fitness_level", "beginner"), "初学者")
    goal = GOAL_LABELS.get(inp.get("goal", "general"), "综合健康")
    equip = EQUIP_LABELS.get(inp.get("equipment", "none"), "无器械")
    days = inp.get("days_per_week", 3)
    medical = inp.get("medical_notes", "")

    parts = [
        f"请根据以下信息为我制定一个周度训练计划：",
        f"年龄：{age}岁，性别：{gender}，身高：{height}cm，体重：{weight}kg",
        f"健身水平：{level}，训练目标：{goal}",
        f"可用器械：{equip}，每周可训练：{days}天",
    ]
    if medical:
        parts.append(f"特殊注意事项：{medical}")
    parts.append("请给出每天的具体动作、组数、次数和要点。")

    return "\n".join(parts)


def _build_qa_user_message(sample: dict) -> str:
    inp = sample.get("input", {})
    question = inp.get("question", inp.get("query", ""))
    detail = inp.get("detail", "")
    user_info = inp.get("user_info", "")

    if question:
        text = question
        if detail:
            text += f"\n\n补充信息：{detail}"
        return text
    if user_info:
        return f"请根据以下用户信息给出健身建议：\n{user_info}"
    # Last resort: use the full input dict
    return json.dumps(inp, ensure_ascii=False)


def convert_sample(sample: dict) -> Optional[dict]:
    """Convert a single pipeline sample to chat messages format."""
    sample_type = sample.get("type", "")
    output_text = sample.get("output", "")

    if not output_text or len(output_text.strip()) < 10:
        return None

    if sample_type in ("action_correction", "exercise_technique"):
        user_msg = _build_correction_user_message(sample)
    elif sample_type == "fitness_planning":
        user_msg = _build_planning_user_message(sample)
    elif sample_type in ("fitness_qa",):
        user_msg = _build_qa_user_message(sample)
    else:
        user_msg = _build_qa_user_message(sample)

    if len(user_msg) < 5:
        return None

    return {
        "messages": [
            {"role": "system", "content": FITNESS_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": output_text.strip()},
        ]
    }


def prepare_training_data(
    input_path: Path = Path("data/processed/fitness_dataset.jsonl"),
    output_dir: Path = Path("data/processed"),
    eval_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[Path, Path]:
    """Convert pipeline JSONL to training/eval chat datasets.

    Returns:
        (train_path, eval_path)
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {input_path}\n"
            f"Run first: python -m code.data_processing.pipeline"
        )

    logger.info("Loading dataset: %s", input_path)
    samples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    logger.info("Loaded %d raw samples", len(samples))

    converted = []
    skipped = 0
    type_counts = {}
    for sample in samples:
        result = convert_sample(sample)
        if result:
            converted.append(result)
            t = sample.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        else:
            skipped += 1

    logger.info("Converted %d samples, skipped %d", len(converted), skipped)
    for t, c in sorted(type_counts.items()):
        logger.info("  %s: %d", t, c)

    random.seed(seed)
    random.shuffle(converted)

    split_idx = int(len(converted) * eval_ratio)
    eval_data = converted[:split_idx]
    train_data = converted[split_idx:]

    train_path = output_dir / "training_data.jsonl"
    eval_path = output_dir / "eval_data.jsonl"

    for path, data in [(train_path, train_data), (eval_path, eval_data)]:
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    logger.info("Train: %d → %s", len(train_data), train_path)
    logger.info("Eval:  %d → %s", len(eval_data), eval_path)

    # Save conversion stats
    stats_path = output_dir / "training_data_stats.json"
    stats = {
        "total_raw": len(samples),
        "total_converted": len(converted),
        "skipped": skipped,
        "train_count": len(train_data),
        "eval_count": len(eval_data),
        "type_distribution": type_counts,
        "system_prompt": FITNESS_SYSTEM_PROMPT,
    }
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    return train_path, eval_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    prepare_training_data()
