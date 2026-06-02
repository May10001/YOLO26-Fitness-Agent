"""
Prompt generator — uses the prompt templates with the existing model wrapper.

Provides:
  1. generate_correction() — structured error → natural guidance text
  2. generate_plan() — user info → weekly plan text
  3. batch_generate_corrections() — batch processing
  4. evaluate_prompt() — prompt quality evaluation
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .templates import PromptBuilder, ErrorGuidancePrompt, PlanningPrompt

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result from a prompt generation call."""
    input_info: dict
    output_text: str
    prompt_messages: list[dict]
    token_count: int = 0
    latency_ms: float = 0.0


class PromptGenerator:
    """Generate fitness guidance using prompt templates + LLM.

    Usage:
        gen = PromptGenerator()
        result = gen.generate_correction(
            exercise="深蹲", detected_error="膝盖内扣", severity=2,
        )
        print(result.output_text)

        plan = gen.generate_plan(
            age=25, weight_kg=70, height_cm=170, gender="男",
            fitness_level="beginner", goal="weight_loss",
            equipment="none", days_per_week=3,
        )
    """

    def __init__(self, model=None):
        """
        Args:
            model: Optional BaseModel instance. If None, uses rule-based generation.
        """
        self.model = model
        self.builder = PromptBuilder()
        self._correction_templates = self._load_correction_templates()
        self._planning_templates = self._load_planning_templates()

    def generate_correction(
        self,
        exercise: str = "",
        detected_error: str = "",
        severity: int = 0,
        phase: str = "",
        score: float = 0,
        error_count: int = 0,
        consecutive_frames: int = 0,
        context: Optional[dict] = None,
        use_llm: bool = False,
        use_fewshot: bool = True,
    ) -> GenerationResult:
        """Generate action correction guidance.

        Args:
            context: Full JSON coaching context dict (preferred).
                     If provided, overrides the individual params.
            exercise, detected_error, severity, ...: Legacy individual params.
                Only used when context is None.

        If use_llm=True and model is available, uses the LLM.
        Otherwise falls back to rule-based template generation.
        """
        if context is not None:
            # New JSON context path
            messages = self.builder.build_correction_prompt(context)
            input_info = dict(context)  # shallow copy
        else:
            # Legacy path: build minimal context from individual params
            context = {
                "exercise": {"cn": exercise, "en": exercise},
                "rep_count": 0,
                "phase": phase,
                "score": {"total": score, "angle": 0, "temporal": 0, "symmetry": 0},
                "joint_angles": {},
                "errors": [
                    {"name": detected_error, "severity": severity, "suggestion": ""}
                ] if detected_error else [],
                "stats": {},
            }
            messages = self.builder.build_correction_prompt(context)
            input_info = {
                "exercise": exercise,
                "detected_error": detected_error,
                "severity": severity,
                "phase": phase,
                "score": score,
            }

        if use_llm and self.model is not None:
            try:
                output = self.model.chat(messages, max_tokens=512)
                return GenerationResult(
                    input_info=input_info,
                    output_text=output,
                    prompt_messages=messages,
                )
            except Exception as e:
                logger.warning("LLM 调用失败，回退到规则生成: %s", e)

        # Rule-based fallback
        ex_name = exercise or context.get("exercise", {}).get("cn", "深蹲")
        err_name = detected_error
        if not err_name and context.get("errors"):
            err_name = context["errors"][0]["name"]
        err_severity = severity or (context.get("errors", [{}])[0].get("severity", 2) if context.get("errors") else 2)
        output = self._rule_based_correction(ex_name, err_name, err_severity)
        return GenerationResult(
            input_info=input_info,
            output_text=output,
            prompt_messages=messages,
        )

    def generate_plan(
        self,
        age: int,
        weight_kg: float,
        height_cm: float,
        gender: str,
        fitness_level: str,
        goal: str,
        equipment: str,
        days_per_week: int,
        medical_notes: str = "",
        preferences: Optional[list[str]] = None,
        use_llm: bool = False,
        use_fewshot: bool = True,
    ) -> GenerationResult:
        """Generate a weekly workout plan.

        If use_llm=True and model is available, uses the LLM.
        Otherwise falls back to rule-based plan generation.
        """
        messages = self.builder.build_planning_prompt(
            age, weight_kg, height_cm, gender,
            fitness_level, goal, equipment, days_per_week,
            medical_notes, preferences,
        )

        input_info = {
            "age": age, "weight_kg": weight_kg, "height_cm": height_cm,
            "gender": gender, "fitness_level": fitness_level, "goal": goal,
            "equipment": equipment, "days_per_week": days_per_week,
            "medical_notes": medical_notes,
        }

        if use_llm and self.model is not None:
            try:
                output = self.model.chat(messages, max_tokens=1024)
                return GenerationResult(
                    input_info=input_info,
                    output_text=output,
                    prompt_messages=messages,
                )
            except Exception as e:
                logger.warning("LLM 调用失败，回退到规则生成: %s", e)

        # Rule-based fallback: use PlanGenerator
        output = self._rule_based_plan(
            age, weight_kg, height_cm, gender,
            fitness_level, goal, equipment, days_per_week,
            medical_notes,
        )
        return GenerationResult(
            input_info=input_info,
            output_text=output,
            prompt_messages=messages,
        )

    def batch_generate_corrections(
        self,
        error_list: list[dict],
        use_llm: bool = False,
    ) -> list[GenerationResult]:
        """Batch generate corrections for a list of error detections."""
        results = []
        for item in error_list:
            result = self.generate_correction(
                exercise=item.get("exercise", "深蹲"),
                detected_error=item.get("error", ""),
                severity=item.get("severity", 2),
                use_llm=use_llm,
            )
            results.append(result)
        return results

    def evaluate_prompt(self, prompt_messages: list[dict]) -> dict:
        """Evaluate prompt quality metrics (heuristic)."""
        system_msg = next((m["content"] for m in prompt_messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in prompt_messages if m["role"] == "user"), "")

        return {
            "system_length": len(system_msg),
            "user_length": len(user_msg),
            "total_messages": len(prompt_messages),
            "fewshot_count": sum(1 for m in prompt_messages if m["role"] == "assistant"),
            "estimated_input_tokens": sum(len(m["content"]) for m in prompt_messages) // 2,
        }

    def _rule_based_correction(self, exercise: str, error: str, severity: int) -> str:
        """Rule-based correction fallback using template library."""
        templates = self._correction_templates
        key = f"{exercise}|{error}"
        if key in templates:
            return templates[key]

        # Generic fallback
        sev_prefix = {
            1: "小提醒：",
            2: "需要注意：",
            3: "⚠ 请立即调整：",
        }
        prefix = sev_prefix.get(severity, "请注意：")
        return f"{prefix}在{exercise}时检测到{error}。建议放慢动作速度，关注正确姿势，必要时减少训练量以确保动作质量。"

    def _rule_based_plan(self, age, weight, height, gender, level, goal, equipment, days, medical) -> str:
        """Rule-based plan generation using existing PlanGenerator."""
        try:
            from code.planning.user_profile import (
                UserProfile, FitnessLevel, FitnessGoal, Equipment,
            )
            from code.planning.plan_generator import PlanGenerator

            level_map = {
                "beginner": FitnessLevel.BEGINNER,
                "intermediate": FitnessLevel.INTERMEDIATE,
                "advanced": FitnessLevel.ADVANCED,
            }
            goal_map = {
                "strength": FitnessGoal.STRENGTH,
                "hypertrophy": FitnessGoal.HYPERTROPHY,
                "endurance": FitnessGoal.ENDURANCE,
                "weight_loss": FitnessGoal.WEIGHT_LOSS,
                "general": FitnessGoal.GENERAL,
            }
            equip_map = {
                "none": Equipment.NONE, "mat": Equipment.MAT,
                "dumbbells": Equipment.DUMBBELLS,
                "resistance_band": Equipment.RESISTANCE_BAND,
                "full_gym": Equipment.FULL_GYM,
            }

            profile = UserProfile(
                name="用户",
                age=age,
                weight_kg=weight,
                height_cm=height,
                fitness_level=level_map.get(level, FitnessLevel.BEGINNER),
                goal=goal_map.get(goal, FitnessGoal.GENERAL),
                equipment=equip_map.get(equipment, Equipment.MAT),
                medical_notes=medical or "",
            )
            generator = PlanGenerator(profile)
            plan = generator.generate_weekly_plan()
            return plan.to_text()
        except Exception as e:
            logger.error("规则生成训练计划失败: %s", e)
            return f"训练计划生成失败: {e}"

    def _load_correction_templates(self) -> dict[str, str]:
        """Load pre-built correction templates."""
        try:
            path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "correction_samples.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                templates = {}
                for item in data:
                    ex = item.get("exercise", "")
                    err = item.get("error", "")
                    out = item.get("output", "")
                    if ex and err and out:
                        templates[f"{ex}|{err}"] = out
                return templates
        except Exception:
            pass

        # Built-in defaults
        return {
            "深蹲|膝盖内扣": "深蹲时膝盖内扣了！下蹲时要有意识地将膝盖向外打开，与脚尖方向一致。可以在膝盖上方套弹力带练习，抵抗弹力带的拉力来激活臀中肌。先减少下蹲深度和次数，等膝盖轨迹稳定后再逐步增加。",
            "深蹲|躯干前倾": "深蹲时身体前倾过多会增加腰椎压力。挺胸收腹，保持背部挺直，目视前方。如果脚踝灵活性不够导致站不稳，可以在脚后跟垫一个小重物来改善下蹲角度。",
            "俯卧撑|塌腰/拱臀": "俯卧撑时髋部下塌了，这会让腰椎受力过大。收紧腹部和臀部，从头到脚踝保持一条直线。如果控制不住，先从跪姿俯卧撑开始练习核心稳定性。",
            "平板支撑|髋部下塌": "平板支撑塌腰了！收紧腹部（肚脐向脊椎方向收）和臀部，身体从头到脚形成一条直线。一旦感觉身体开始变形就停下来，不要硬撑。",
            "卷腹|颈部用力": "卷腹时脖子在用劲！双手轻放耳侧不要用力拉头，下巴微收保持一拳距离，集中注意力用腹部发力卷起身体。如果还是脖子疼，双臂交叉放在胸前做。",
            "开合跳|缓冲不足": "落地声太大了说明缓冲不够！落地时膝盖和髋部微屈吸收冲击力，想象脚掌从脚尖到脚跟滚动落地。减小跳跃高度，专注'轻落地'的感觉。",
        }

    def _load_planning_templates(self) -> dict:
        return {}


def demo():
    """Run a quick demo of the prompt generator."""
    logging.basicConfig(level=logging.INFO)

    gen = PromptGenerator()

    # Demo 1: Correction
    print("=" * 60)
    print("Demo 1: 动作纠错")
    print("=" * 60)
    result = gen.generate_correction(
        exercise="深蹲",
        detected_error="膝盖内扣",
        severity=2,
        phase="低位",
        score=55,
    )
    print(f"Prompt messages: {len(result.prompt_messages)} 条")
    print(f"Output: {result.output_text[:200]}...")
    print()

    # Demo 2: Planning
    print("=" * 60)
    print("Demo 2: 训练计划")
    print("=" * 60)
    result = gen.generate_plan(
        age=25, weight_kg=70, height_cm=170, gender="男",
        fitness_level="beginner", goal="weight_loss",
        equipment="none", days_per_week=3,
    )
    print(f"Prompt messages: {len(result.prompt_messages)} 条")
    print(f"Output:\n{result.output_text[:500]}...")
    print()

    # Demo 3: Prompt evaluation
    print("=" * 60)
    print("Demo 3: Prompt 质量评估")
    print("=" * 60)
    context = {
        "exercise": {"cn": "深蹲", "en": "squat"},
        "rep_count": 6,
        "phase": "离心收缩",
        "score": {"total": 55, "angle": 20, "temporal": 20, "symmetry": 15},
        "joint_angles": {
            "knee": {"left": 75, "right": 68},
            "hip": {"left": 65, "right": 70},
            "elbow": {"left": None, "right": None},
            "shoulder": {"left": None, "right": None},
            "trunk": 30,
            "ankle": {"left": 25, "right": 28},
        },
        "errors": [
            {"name": "膝盖内扣", "severity": 2, "suggestion": "保持膝盖与脚尖方向一致"}
        ],
        "stats": {
            "best_score": 72, "avg_recent_score": 58,
            "consecutive_good": 0, "consecutive_bad": 3,
            "error_ranking": {"膝盖内扣": 5, "深度不足": 2},
        },
    }
    messages = gen.builder.build_correction_prompt(context)
    quality = gen.evaluate_prompt(messages)
    for k, v in quality.items():
        print(f"  {k}: {v}")

    # Demo 4: Batch generation
    print("\n" + "=" * 60)
    print("Demo 4: 批量生成")
    print("=" * 60)
    errors = [
        {"exercise": "深蹲", "error": "膝盖内扣", "severity": 2},
        {"exercise": "俯卧撑", "error": "塌腰/拱臀", "severity": 2},
        {"exercise": "卷腹", "error": "颈部用力", "severity": 1},
    ]
    results = gen.batch_generate_corrections(errors)
    for r in results:
        print(f"  [{r.input_info['exercise']}] {r.input_info['detected_error']}: {r.output_text[:80]}...")


if __name__ == "__main__":
    demo()
