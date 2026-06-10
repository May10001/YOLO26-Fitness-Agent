"""
LoRA fine-tuning pipeline for Qwen2.5 on Chinese fitness domain data.

Supports multiple model sizes with automatic hardware adaptation:
  - CPU: full fp32 + LoRA (small models only: 0.5B, 1.5B)
  - GPU <8GB VRAM: 4-bit QLoRA (all models)
  - GPU >=16GB VRAM: fp16 + LoRA (up to 7B)

Usage:
    # Default: train Qwen2.5-1.5B on the full pipeline dataset
    python -m code.models.fine_tuning.trainer

    # Train a specific model
    python -m code.models.fine_tuning.trainer --model 0.5B
    python -m code.models.fine_tuning.trainer --model 7B

    # Quick test with built-in small dataset only
    python -m code.models.fine_tuning.trainer --use-builtin-data
"""

import json
import logging
from argparse import ArgumentParser
from datetime import datetime
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

logger = logging.getLogger(__name__)

# ── Model Registry ──────────────────────────────────────────────────────────
# Based on model_selection/compare.py analysis. Fitness scores reflect
# Chinese capability, VRAM accessibility, inference speed, context length,
# and LoRA fine-tuning cost for the fitness domain.

MODEL_REGISTRY = {
    "0.5B": {
        "hf_id": "Qwen/Qwen2.5-0.5B-Instruct",
        "params_b": 0.5,
        "vram_fp16_gb": 1.0,
        "vram_int4_gb": 0.3,
        "ceval": 52.3,
        "fitness_score": 5.0,
        "recommendation": "边缘设备实时纠错 / CPU训练",
        "max_seq_length": 512,
        "lora_rank": 16,
        "lora_alpha": 32,
    },
    "1.5B": {
        "hf_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "params_b": 1.5,
        "vram_fp16_gb": 3.0,
        "vram_int4_gb": 0.9,
        "ceval": 64.8,
        "fitness_score": 6.5,
        "recommendation": "★ 主力推荐：消费级GPU可微调，中文能力足够健身领域",
        "max_seq_length": 512,
        "lora_rank": 16,
        "lora_alpha": 32,
    },
    "3B": {
        "hf_id": "Qwen/Qwen2.5-3B-Instruct",
        "params_b": 3.0,
        "vram_fp16_gb": 6.0,
        "vram_int4_gb": 1.8,
        "ceval": 74.5,
        "fitness_score": 7.5,
        "recommendation": "★ VRAM与性能的最佳甜点，RTX 4060 8GB可微调",
        "max_seq_length": 512,
        "lora_rank": 16,
        "lora_alpha": 32,
    },
    "7B": {
        "hf_id": "Qwen/Qwen2.5-7B-Instruct",
        "params_b": 7.0,
        "vram_fp16_gb": 14.0,
        "vram_int4_gb": 4.5,
        "ceval": 82.3,
        "fitness_score": 8.0,
        "recommendation": "服务器端深度问答 / 复杂训练规划",
        "max_seq_length": 1024,
        "lora_rank": 16,
        "lora_alpha": 32,
    },
}

DEFAULT_MODEL = "1.5B"
DEFAULT_OUTPUT_DIR = Path("./lora_fitness_adapter")

# LoRA target modules for Qwen2.5 architecture
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]


def get_lora_config(rank: int = 16, alpha: int = 32, dropout: float = 0.05) -> LoraConfig:
    return LoraConfig(
        r=rank,
        lora_alpha=alpha,
        lora_dropout=dropout,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )


def get_training_args(
    output_dir: Path,
    num_epochs: int = 3,
    batch_size: int = 2,
    learning_rate: float = 2e-4,
    warmup_steps: int = 50,
    use_bf16: bool = False,
) -> TrainingArguments:
    import inspect

    candidate_kwargs = {
        "output_dir": str(output_dir),
        "per_device_train_batch_size": batch_size,
        "gradient_accumulation_steps": 4,
        "num_train_epochs": num_epochs,
        "learning_rate": learning_rate,
        "fp16": not use_bf16 and torch.cuda.is_available(),
        "bf16": use_bf16,
        "save_total_limit": 2,
        "logging_steps": 10,
        "save_steps": 100,
        "eval_steps": 100,
        "eval_strategy": "steps",
        "lr_scheduler_type": "cosine",
        "warmup_steps": warmup_steps,
        "remove_unused_columns": False,
        "dataloader_pin_memory": False,
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
    }

    # Filter to only params this transformers version accepts
    sig = inspect.signature(TrainingArguments.__init__)
    valid_params = set(sig.parameters.keys())
    filtered_kwargs = {k: v for k, v in candidate_kwargs.items() if k in valid_params}

    skipped = set(candidate_kwargs) - set(filtered_kwargs)
    if skipped:
        logger.info("Skipping unsupported TrainingArguments params: %s", sorted(skipped))

    return TrainingArguments(**filtered_kwargs)


def load_chat_dataset(jsonl_path: Path) -> Dataset:
    """Load a JSONL file where each line has a 'messages' field."""
    data = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return Dataset.from_list(data)


def fine_tune(
    model_size: str = DEFAULT_MODEL,
    train_dataset: Optional[Dataset] = None,
    eval_dataset: Optional[Dataset] = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    num_epochs: int = 3,
    batch_size: int = 2,
    learning_rate: float = 2e-4,
    resume_from_checkpoint: Optional[str] = None,
    use_builtin_data: bool = False,
) -> Path:
    """Run LoRA fine-tuning on Qwen2.5 with fitness domain data.

    Args:
        model_size: Key into MODEL_REGISTRY ("0.5B", "1.5B", "3B", "7B").
        train_dataset: Training dataset in chat-messages format.
                       If None, loads from data/processed/training_data.jsonl
                       (or falls back to built-in data if use_builtin_data=True).
        eval_dataset: Evaluation dataset. If None, loads from data/processed/eval_data.jsonl.
        output_dir: Where to save LoRA adapter weights.
        num_epochs: Training epochs.
        batch_size: Per-device batch size.
        learning_rate: Peak learning rate (cosine schedule).
        resume_from_checkpoint: Resume from a previous checkpoint directory.
        use_builtin_data: If True, use the small handwritten dataset from fitness_data.py
                          instead of the full pipeline dataset.

    Returns:
        Path to the saved adapter directory.
    """
    if model_size not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model size: {model_size}. Choose from: {list(MODEL_REGISTRY.keys())}"
        )

    cfg = MODEL_REGISTRY[model_size]
    model_name = cfg["hf_id"]
    max_seq_length = cfg["max_seq_length"]
    lora_rank = cfg["lora_rank"]
    lora_alpha = cfg["lora_alpha"]

    use_gpu = torch.cuda.is_available()
    device = "cuda" if use_gpu else "cpu"
    vram_key = "vram_int4_gb" if use_gpu else "vram_fp16_gb"
    est_vram = cfg[vram_key]

    logger.info("=" * 60)
    logger.info("Model: %s (%s)", model_name, model_size)
    logger.info("Params: %.1fB | VRAM est: %.1fGB | C-Eval: %.1f",
                cfg["params_b"], est_vram, cfg["ceval"])
    logger.info("Recommendation: %s", cfg["recommendation"])
    logger.info("Device: %s", device.upper())
    logger.info("=" * 60)

    # ── Tokenizer ──────────────────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── Model loading (hardware-adaptive) ──────────────────────────────────
    if use_gpu:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        logger.info("GPU VRAM: %.1f GB", vram_gb)

        # RTX 5090 / A100 / etc: use bf16 if supported, else fp16
        use_bf16 = torch.cuda.is_bf16_supported()
        train_dtype = torch.bfloat16 if use_bf16 else torch.float16
        dtype_label = "bf16" if use_bf16 else "fp16"

        if vram_gb >= 18:
            # 24GB+ GPUs: fp16/bf16 for all models including 7B
            logger.info("Loading %s model (%s, ample VRAM)", dtype_label, model_size)
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=train_dtype,
                device_map="auto",
                trust_remote_code=True,
            )
        elif vram_gb >= 12 and model_size in ("0.5B", "1.5B", "3B"):
            # 12-16GB GPUs: fp16/bf16 for smaller models
            logger.info("Loading %s model (%s, moderate VRAM)", dtype_label, model_size)
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=train_dtype,
                device_map="auto",
                trust_remote_code=True,
            )
        else:
            # Use 4-bit QLoRA
            logger.info("Loading 4-bit quantized model (QLoRA)")
            from transformers import BitsAndBytesConfig
            from peft import prepare_model_for_kbit_training
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
            )
            model = prepare_model_for_kbit_training(model)
    else:
        logger.info("CPU mode: loading fp32 model (expect slow training)")
        if model_size not in ("0.5B", "1.5B"):
            logger.warning(
                "%s on CPU will be extremely slow and may OOM. "
                "Consider using 0.5B or 1.5B.", model_size
            )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )

    # ── Apply LoRA ─────────────────────────────────────────────────────────
    peft_config = get_lora_config(rank=lora_rank, alpha=lora_alpha)
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # ── Dataset ────────────────────────────────────────────────────────────
    if train_dataset is None:
        pipeline_train = Path("data/processed/training_data.jsonl")

        if not use_builtin_data and pipeline_train.exists():
            logger.info("Loading full pipeline dataset")
            train_dataset = load_chat_dataset(pipeline_train)
        else:
            if not pipeline_train.exists() and not use_builtin_data:
                logger.info("Pipeline dataset not found, falling back to built-in data")
                logger.info("Run first: python -m code.models.fine_tuning.prepare_data")
            else:
                logger.info("Using built-in handwritten dataset (--use-builtin-data)")
            from .fitness_data import get_fitness_dataset
            train_dataset = get_fitness_dataset()

    if eval_dataset is None:
        pipeline_eval = Path("data/processed/eval_data.jsonl")
        if pipeline_eval.exists():
            eval_dataset = load_chat_dataset(pipeline_eval)
            logger.info("Eval samples: %d", len(eval_dataset))

    logger.info("Train samples: %d", len(train_dataset))

    # ── Training ───────────────────────────────────────────────────────────
    from trl import SFTTrainer
    import inspect

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) / f"{model_size}_{timestamp}"

    training_args = get_training_args(
        output_dir=run_dir,
        num_epochs=num_epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        use_bf16=use_gpu and torch.cuda.is_bf16_supported(),
    )

    # Build kwargs dict, then filter to only what this trl version accepts.
    # trl has renamed/removed params across versions (tokenizer→processing_class,
    # max_seq_length removed, dataset_text_field removed, packing removed).
    sig = inspect.signature(SFTTrainer.__init__)
    valid_params = set(sig.parameters.keys())

    candidate_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_dataset,
        "eval_dataset": eval_dataset,
        "max_seq_length": max_seq_length,
        "dataset_text_field": "messages",
        "packing": False,
    }

    # Pick the right tokenizer parameter name
    if "processing_class" in valid_params:
        candidate_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in valid_params:
        candidate_kwargs["tokenizer"] = tokenizer

    # Keep only params the installed SFTTrainer actually accepts
    filtered_kwargs = {k: v for k, v in candidate_kwargs.items() if k in valid_params}

    skipped = set(candidate_kwargs) - set(filtered_kwargs)
    if skipped:
        logger.info("Skipping unsupported SFTTrainer params: %s", sorted(skipped))

    trainer = SFTTrainer(**filtered_kwargs)

    logger.info("Starting training...")
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    # ── Save ───────────────────────────────────────────────────────────────
    adapter_dir = run_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    # Save training config for reproducibility
    config = {
        "model_size": model_size,
        "hf_id": model_name,
        "params_b": cfg["params_b"],
        "ceval": cfg["ceval"],
        "fitness_score": cfg["fitness_score"],
        "lora_rank": lora_rank,
        "lora_alpha": lora_alpha,
        "max_seq_length": max_seq_length,
        "num_epochs": num_epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "train_samples": len(train_dataset),
        "eval_samples": len(eval_dataset) if eval_dataset else 0,
        "device": device,
        "timestamp": timestamp,
    }
    with open(adapter_dir / "training_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    logger.info("Adapter saved to: %s", adapter_dir)
    return adapter_dir


def main():
    parser = ArgumentParser(description="LoRA fine-tune Qwen2.5 for fitness domain")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        choices=list(MODEL_REGISTRY.keys()),
        help="Model size to fine-tune (default: 1.5B)"
    )
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for LoRA adapter"
    )
    parser.add_argument(
        "--epochs", type=int, default=3,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size", type=int, default=2,
        help="Per-device batch size"
    )
    parser.add_argument(
        "--learning-rate", type=float, default=2e-4,
        help="Peak learning rate"
    )
    parser.add_argument(
        "--use-builtin-data", action="store_true",
        help="Use small built-in dataset instead of full pipeline dataset"
    )
    parser.add_argument(
        "--resume", default=None,
        help="Resume from checkpoint directory"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Ensure training data is prepared
    train_path = Path("data/processed/training_data.jsonl")
    if not train_path.exists() and not args.use_builtin_data:
        logger.info("Training data not found, preparing from pipeline dataset...")
        from .prepare_data import prepare_training_data
        try:
            prepare_training_data()
        except FileNotFoundError:
            logger.warning(
                "Pipeline dataset not found. Run 'python -m code.data_processing.pipeline' "
                "first, or use --use-builtin-data for the small handwritten dataset."
            )
            return

    adapter_path = fine_tune(
        model_size=args.model,
        output_dir=Path(args.output_dir),
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        resume_from_checkpoint=args.resume,
        use_builtin_data=args.use_builtin_data,
    )

    print(f"\n{'=' * 60}")
    print(f"Fine-tuning complete!")
    print(f"Adapter saved to: {adapter_path}")
    print(f"\nTo use the fine-tuned model:")
    print(f"  from code.models.fitness_assistant import FitnessAssistant")
    print(f"  assistant = FitnessAssistant(lora_path='{adapter_path}')")
    print(f"  reply = assistant.chat('深蹲时膝盖内扣怎么办？')")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
