"""
LoRA fine-tuning pipeline for Qwen2.5-0.5B-Instruct on fitness domain.

CPU-compatible: loads full fp32 model and applies LoRA (not QLoRA).
GPU users can enable 4-bit quantization by uncommenting the bnb config.
"""

import logging
from pathlib import Path
from typing import Optional

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
)
from trl import SFTTrainer

from .fitness_data import get_fitness_dataset

logger = logging.getLogger(__name__)

LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

DEFAULT_OUTPUT_DIR = Path("./lora_fitness_adapter")
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"


def get_lora_config() -> LoraConfig:
    return LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )


def get_training_args(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    num_epochs: int = 3,
    batch_size: int = 2,
    learning_rate: float = 2e-4,
) -> TrainingArguments:
    return TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        num_train_epochs=num_epochs,
        learning_rate=learning_rate,
        fp16=False,
        save_total_limit=2,
        logging_steps=10,
        save_steps=100,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        report_to=None,
        remove_unused_columns=False,
        dataloader_pin_memory=False,
    )


def fine_tune(
    dataset: Optional[Dataset] = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    num_epochs: int = 3,
    batch_size: int = 2,
    resume_from_checkpoint: Optional[str] = None,
) -> Path:
    """Run LoRA fine-tuning and save adapter weights.

    On CPU: loads full fp32 model + LoRA (~2M trainable params).
    On GPU: uses 4-bit QLoRA for memory efficiency.

    Args:
        dataset: Training dataset. If None, uses the built-in fitness dataset.
        output_dir: Directory to save LoRA adapter weights.
        num_epochs: Number of training epochs.
        batch_size: Per-device batch size.
        resume_from_checkpoint: Path to a previous checkpoint to resume from.

    Returns:
        Path to the saved adapter directory.
    """
    if dataset is None:
        dataset = get_fitness_dataset()

    use_gpu = torch.cuda.is_available()
    device = "cuda" if use_gpu else "cpu"
    logger.info("Training on: %s", device.upper())

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load model
    if use_gpu:
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        from peft import prepare_model_for_kbit_training
        model = prepare_model_for_kbit_training(model)
    else:
        logger.info("CPU mode: loading full fp32 model for LoRA training")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )

    lora_config = get_lora_config()
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = get_training_args(
        output_dir=output_dir,
        num_epochs=num_epochs,
        batch_size=batch_size,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        max_seq_length=512,
        dataset_text_field="messages",
        packing=False,
    )

    trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    logger.info("LoRA adapter saved to: %s", output_dir)
    return output_dir


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    fine_tune()
