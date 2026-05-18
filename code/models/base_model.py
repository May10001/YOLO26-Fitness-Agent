"""
Shared model loader for Qwen2.5-Instruct series.
Supports 0.5B / 1.5B / 3B / 7B with LoRA adapter injection.

Default model is Qwen2.5-1.5B-Instruct (best VRAM/capability balance).
"""

import logging
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

# Model registry — mirrors fine_tuning/trainer.py MODEL_REGISTRY
MODEL_VARIANTS = {
    "0.5B": "Qwen/Qwen2.5-0.5B-Instruct",
    "1.5B": "Qwen/Qwen2.5-1.5B-Instruct",
    "3B": "Qwen/Qwen2.5-3B-Instruct",
    "7B": "Qwen/Qwen2.5-7B-Instruct",
}

DEFAULT_MODEL_SIZE = "1.5B"
DEFAULT_MAX_TOKENS = 512


class BaseModel:
    """Singleton wrapper around Qwen2.5-Instruct.

    Usage:
        model = BaseModel.get_instance()                    # default 1.5B
        model = BaseModel.get_instance(model_size="0.5B")   # edge device
        model = BaseModel.get_instance(model_size="7B")     # server quality
        reply = model.chat([
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
        ])
    """

    _instance: Optional["BaseModel"] = None
    _model = None
    _tokenizer = None
    _current_model_size: Optional[str] = None

    def __init__(
        self,
        lora_path: Optional[str] = None,
        model_size: str = DEFAULT_MODEL_SIZE,
    ):
        if model_size not in MODEL_VARIANTS:
            raise ValueError(
                f"Unknown model size: {model_size}. Choose from: {list(MODEL_VARIANTS.keys())}"
            )

        model_name = MODEL_VARIANTS[model_size]

        # Reuse if same model already loaded
        if BaseModel._model is not None and BaseModel._current_model_size == model_size:
            logger.info("Reusing already-loaded base model (%s)", model_size)
            return

        # If switching model size, clear old instance
        if BaseModel._model is not None:
            logger.info("Switching model from %s to %s", BaseModel._current_model_size, model_size)
            BaseModel.reset_instance()

        logger.info("Loading base model: %s (%s)", model_name, model_size)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="right",
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        load_kwargs = {
            "trust_remote_code": True,
        }
        if self.device == "cuda":
            load_kwargs.update({
                "torch_dtype": torch.float16,
                "device_map": "auto",
            })
        else:
            load_kwargs.update({
                "dtype": torch.float32,
                "device_map": "cpu",
                "low_cpu_mem_usage": True,
            })

        self.model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
        self.model.eval()

        if lora_path is not None:
            logger.info("Loading LoRA adapter from: %s", lora_path)
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, lora_path)
            self.model.eval()

        BaseModel._model = self.model
        BaseModel._tokenizer = self.tokenizer
        BaseModel._current_model_size = model_size

    @classmethod
    def get_instance(
        cls,
        lora_path: Optional[str] = None,
        model_size: str = DEFAULT_MODEL_SIZE,
    ) -> "BaseModel":
        if cls._instance is None or cls._current_model_size != model_size:
            cls._instance = cls(lora_path=lora_path, model_size=model_size)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Clear the singleton (useful for swapping adapters or model sizes)."""
        cls._instance = None
        cls._model = None
        cls._tokenizer = None
        cls._current_model_size = None
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
