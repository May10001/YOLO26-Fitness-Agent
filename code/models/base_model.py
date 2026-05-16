"""
Shared model loader for Qwen2.5-0.5B-Instruct.
Supports both base inference and LoRA-adapter inference.
"""

import logging
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_MAX_TOKENS = 512


class BaseModel:
    """Singleton wrapper around Qwen2.5-0.5B-Instruct.

    Usage:
        model = BaseModel.get_instance()
        reply = model.chat([
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
        ])
    """

    _instance: Optional["BaseModel"] = None
    _model = None
    _tokenizer = None

    def __init__(self, lora_path: Optional[str] = None):
        if BaseModel._model is not None:
            logger.info("Reusing already-loaded base model")
            return

        logger.info("Loading base model: %s", MODEL_NAME)
        self.device = "cpu"
        self.dtype = torch.float32

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            trust_remote_code=True,
            padding_side="right",
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            dtype=self.dtype,
            device_map="cpu",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        self.model.eval()

        if lora_path is not None:
            logger.info("Loading LoRA adapter from: %s", lora_path)
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, lora_path)
            self.model.eval()

        BaseModel._model = self.model
        BaseModel._tokenizer = self.tokenizer

    @classmethod
    def get_instance(cls, lora_path: Optional[str] = None) -> "BaseModel":
        if cls._instance is None:
            cls._instance = cls(lora_path=lora_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Clear the singleton (useful for swapping adapters)."""
        cls._instance = None
        cls._model = None
        cls._tokenizer = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        """Generate a response given a conversation history.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            max_tokens: Maximum new tokens to generate.

        Returns:
            Generated text (stripped).
        """
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer([text], return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        generated = outputs[0][inputs["input_ids"].shape[1]:]
        reply = self.tokenizer.decode(generated, skip_special_tokens=True)
        return reply.strip()
