# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

YOLO26-Fitness-Agent is a real-time AI fitness coach combining YOLO26 pose estimation with Qwen2.5 LLMs. It detects exercise form via webcam, scores movements, identifies 10+ error types, and generates coaching guidance in Chinese. The project targets a CVPR2026 workshop paper.

## Commands

```bash
# Install dependencies (openai + dashscope needed for remote API mode)
pip install -r requirements.txt openai dashscope

# Run the unified Tkinter GUI (real-time webcam fitness monitoring + AI chat)
python -m code.workout_app --model yolo26n-pose.pt

# Run unit tests (44 test cases)
python -m pytest tests/test_pose_analyzer.py -v

# Self-test individual modules
python -m code.pose_analyzer       # Pose analysis engine
python -m code.visualization       # Visualization module

# Generate the fitness fine-tuning dataset (outputs to data/processed/)
python -m code.data_processing.pipeline

# Generate model comparison report
python -m code.model_selection.compare

# Test remote API connectivity (DashScope Qwen2.5-7B, no local GPU)
python scripts/test_remote_api.py
python scripts/test_remote_api.py -q "如何做标准俯卧撑？"
python scripts/test_remote_api.py -m          # multi-turn chat mode

# LoRA fine-tuning
python -m code.models.fine_tuning.trainer                    # default 1.5B
python -m code.models.fine_tuning.trainer --model 7B         # full quality
python -m code.models.fine_tuning.trainer --use-builtin-data # quick test
```

## Architecture

### Data flow

```
Webcam → YOLO26 pose (17 keypoints) → PoseAnalyzer → ContextEngine → guidance text
                                                      → JointAngleHeatmap → ASCII heatmap
                                User query → FitnessAgent.chat() → Qwen2.5 (+LoRA) → reply
                                UserProfile → PlanGenerator → weekly workout plan
                                AnalysisResult + GuidanceState → RealTimeCoach → DashScope API → chat panel
```

### Key modules

- **`code/pose_analyzer.py`** — Core engine. Extracts 10 joint angles from 17 COCO keypoints, scores movements on 3 dimensions (angle 40pts + temporal 30pts + symmetry 30pts), applies EMA/median-filter temporal smoothing, and detects 10+ error types (knee valgus, arched back, neck compensation, etc.). Defines `EXERCISE_STANDARDS` with angle thresholds for all 10 exercises.

- **`code/agent.py`** — `FitnessAgent` orchestrator. Lazy-initializes `DialogueAssistant`, `FitnessAssistant`, `ContextEngine`, and `PlanGenerator`. Auto-routes chat messages: if the message contains Chinese fitness keywords → `FitnessAssistant` (with LoRA + pose context), otherwise → `DialogueAssistant` (general Qwen2.5).

- **`code/realtime_coach.py`** — Real-time LLM coaching engine. Consumes per-frame `AnalysisResult` + `GuidanceState`, builds structured Chinese context strings, evaluates triggers (severe error, score drop, milestone, personal best, good streak), and manages rate limiting (cooldowns per type + global 6s minimum). Contains `CoachContextBuilder`, `CoachTriggerEvaluator`, and `RealTimeCoach` classes.

- **`code/coach_system_prompt.py`** — System prompt and context templates for the fine-tuned coach model. Contains `COACH_SYSTEM_PROMPT` (full, for reactive chat), `COACH_SYSTEM_PROMPT_PROACTIVE` (shorter, for auto-push), and `COACH_CONTEXT_TEMPLATE` / `COACH_REACTIVE_TEMPLATE` for structured context formatting.

- **`code/models/base_model.py`** — Singleton `BaseModel` wrapping Qwen2.5-Instruct (0.5B/1.5B/3B/7B) with optional LoRA adapter injection via PEFT. Handles device placement (CUDA/CPU), tokenizer setup, and chat template formatting.

- **`code/models/fitness_assistant.py`** — Fitness-domain chat model with a specialized system prompt and LoRA adapter for Chinese fitness Q&A.

- **`code/models/dialogue_assistant.py`** — General-purpose chat model (no LoRA, base Qwen2.5).

- **`code/guidance/context_engine.py`** — Per-frame coaching engine. Consumes `AnalysisResult`, tracks state (rep count, consecutive good/bad form, error counters), and emits `GuidanceMessage`s of 4 types: form correction, performance feedback, motivation, safety warning. Has cooldown logic to avoid spam.

- **`code/visualization.py`** — `JointAngleHeatmap` class for comparing user joint angles against standard reference ranges per exercise. Computes deviation matrices (good/warning/bad) and generates ASCII terminal heatmaps.

- **`code/planning/plan_generator.py`** — Rule-based weekly workout plan generation with progressive overload. Takes `UserProfile` (level, goal, equipment, days/week) and outputs structured plans for 5 training goals.

- **`code/planning/user_profile.py`** — `UserProfile` dataclass with JSON persistence to `user_profiles/` directory.

- **`code/workout_app.py`** — The unified Tkinter GUI. Multi-threaded: a `DetectionThread` handles webcam→YOLO→analysis→guidance and pushes `DetectionResult` frames to a `queue.Queue`; the main thread polls the queue and updates UI (video, scores, errors, guidance text). Includes an embedded Qwen2.5 chat panel, session history with JSON persistence, and settings for model/camera/confidence.

- **`code/models/fine_tuning/trainer.py`** — LoRA fine-tuning pipeline with automatic hardware adaptation (QLoRA 4-bit for <8GB VRAM, fp16 LoRA for ≥16GB). Supports 0.5B/1.5B/3B/7B models.

- **`code/data_processing/pipeline.py`** — End-to-end dataset construction: cleaning → annotation → JSONL output (1626 samples across action correction, planning, and Q&A).

### Top-level files

- `workingout_monitoring.py` — Older Tkinter GUI (pose detection only, no AI chat). Superseded by `code/workout_app.py`.
- `workingout_monitoring_ai.py` — Older Tkinter GUI (pose + chat, without ContextEngine). Superseded by `code/workout_app.py`.
- `yolo26n-pose.pt` — YOLO26 nano pose model weights (~7.9 MB, tracked via Git LFS).
- `data/processed/fitness_dataset.json` — The cleaned/annotated training dataset.

## Model recommendations (from model_selection/compare.py)

| Scenario | Model | Quant | VRAM | Latency |
|----------|-------|-------|------|---------|
| Edge real-time | Qwen2.5-1.5B | INT4 | ~1GB | <30ms |
| Mobile offline | Qwen2.5-0.5B | INT4 | ~0.3GB | <50ms |
| Server planning | Qwen2.5-7B | INT8 | ~8GB | <2s |
| Deep fitness Q&A | Qwen2.5-7B | FP16 | ~14GB | <3s |

## Remote API (DashScope)

The project supports two chat backends, toggled via the GUI settings panel:

| Mode | What it does | Requirements |
|------|-------------|--------------|
| **Remote (recommended)** | OpenAI-compatible → DashScope → Qwen2.5-7B + LoRA | `pip install openai`, API key |
| Local | HuggingFace → Qwen2.5 0.5B~7B | `torch`, `transformers`, GPU RAM |

**Remote API config** (`data/api_config.json`, gitignored):

```json
{
    "use_remote": true,
    "api_key": "sk-427b5295e2884e1183491ee9ab8b5e16",
    "model_code": "qwen2.5-7b-instruct-d1a1cabf17c2-yzqr"
}
```

- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- The API key belongs to the DashScope account that owns the deployment — only the creator's key works.
- `data/api_config.json` is in `.gitignore` to prevent credential leaks.
- Test connectivity with `python scripts/test_remote_api.py` before launching the GUI.

## Important patterns

- **Lazy initialization**: `FitnessAgent` properties (`dialogue`, `fitness`, `guidance_engine`) are lazily created on first access to defer model loading.
- **Singleton model**: `BaseModel` uses a class-level singleton. Call `BaseModel.get_instance(model_size="1.5B")` to get or create the shared instance. Use `BaseModel.reset_instance()` when swapping adapters.
- **Multi-threaded GUI**: Detection runs in a daemon thread, UI updates happen on the main thread via `queue.Queue` polling (`_poll_queue` every 10ms). Never update Tkinter widgets from the detection thread.
- **Chinese-first**: All user-facing text, prompts, guidance, and UI are in Chinese. Exercise names use Chinese throughout the codebase with `EXERCISE_ENGLISH_NAMES` mapping for display.
