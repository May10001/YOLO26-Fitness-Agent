"""
Fitness model wrapper — with LoRA adapter for fitness domain expertise.
"""

from typing import Optional

from .base_model import BaseModel

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


class FitnessAssistant:
    """Fitness-domain expert assistant using Qwen2.5-Instruct + LoRA.

    The LoRA adapter is fine-tuned on Chinese fitness Q&A data.
    If the adapter path is None, falls back to the base model with
    a fitness-specific system prompt.

    Args:
        lora_path: Path to a LoRA adapter directory (from fine_tuning.trainer).
        model_size: Base model size: "0.5B", "1.5B", "3B", or "7B".
                    Default "1.5B" is the recommended VRAM/capability balance.
    """

    def __init__(
        self,
        lora_path: Optional[str] = None,
        model_size: str = "1.5B",
    ):
        self.lora_path = lora_path
        self.model_size = model_size
        self.model = BaseModel.get_instance(
            lora_path=lora_path,
            model_size=model_size,
        )

    def chat(
        self,
        user_message: str,
        pose_context: Optional[str] = None,
        coach_context_json: Optional[dict] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """Respond to a fitness-related query.

        Args:
            user_message: The user's question or command.
            pose_context: Optional string describing the user's current
                          exercise form (from ContextEngine guidance).
                          Deprecated in favor of coach_context_json.
            coach_context_json: Optional dict with full coaching context
                                (exercise, rep_count, phase, score,
                                 joint_angles, errors, stats).
                                When provided, it is serialized as JSON
                                and placed in the user message for the
                                model to parse.
            max_tokens: Maximum generated tokens.

        Returns:
            Fitness advice text.
        """
        import json

        if coach_context_json is not None:
            # New JSON format: context as structured JSON in user message
            context_str = json.dumps(coach_context_json, ensure_ascii=False, indent=2)
            content = f"{context_str}\n\n[用户提问]\n{user_message}"
        elif pose_context:
            content = f"[实时姿态分析]\n{pose_context}\n\n[用户提问]\n{user_message}"
        else:
            content = user_message

        messages = [
            {"role": "system", "content": FITNESS_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        return self.model.chat(messages, max_tokens=max_tokens, temperature=temperature)
