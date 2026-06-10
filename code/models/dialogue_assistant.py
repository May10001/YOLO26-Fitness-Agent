"""
Dialogue model wrapper — no fine-tuning, general conversation.
"""

from .base_model import BaseModel

DIALOGUE_SYSTEM_PROMPT = (
    "你是一个有帮助的AI助手。你可以回答各种问题，包括日常对话、知识问答、"
    "生活建议等。请用中文回答，保持友好和专业的语气。"
)


class DialogueAssistant:
    """General-purpose dialogue assistant using base Qwen2.5-Instruct.

    No LoRA adapter is loaded. Suitable for open-ended conversation.
    """

    def __init__(self, model_size: str = "1.5B"):
        self.model_size = model_size
        self.model = BaseModel.get_instance(model_size=model_size)

    def chat(
        self,
        user_message: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """Respond to a user message in a general conversation."""
        messages = [
            {"role": "system", "content": DIALOGUE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        return self.model.chat(messages, max_tokens=max_tokens, temperature=temperature)
