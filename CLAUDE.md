# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

YOLO26-Fitness-Agent is a real-time AI fitness coach combining YOLO26 pose estimation with Qwen2.5 LLMs. It detects exercise form via webcam, scores movements, identifies 10+ error types, and generates coaching guidance in Chinese. The project targets a CVPR2026 workshop paper.

## Commands

```bash
# Install dependencies (openai + dashscope needed for remote API mode)
pip install -r requirements.txt openai dashscope

# --- Web Frontend (Vue 3 + FastAPI) ---
# Start backend (from project root)
cd /path/to/YOLO26-Fitness-Agent
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Start frontend (in a separate terminal)
cd frontend
npm install
npm run dev
# Frontend runs at http://localhost:5173, proxies /ws and /api to backend :8000

# --- Desktop GUI (Tkinter, legacy) ---
# Run the unified Tkinter GUI (real-time webcam fitness monitoring + AI chat)
python -m code.workout_app --model yolo26n-pose.pt

# Run unit tests (44 test cases)
python -m pytest tests/test_pose_analyzer.py -v

# Run a single test by name
python -m pytest tests/test_pose_analyzer.py -v -k "test_squat_scoring"

# Self-test individual modules
python -m code.pose_analyzer       # Pose analysis engine
python -m code.visualization       # Visualization module

# Generate the fitness fine-tuning dataset (outputs to data/processed/)
python -m code.data_processing.pipeline

# Convert dataset to training format (train/eval split)
python -m code.models.fine_tuning.prepare_data

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

### Environment variables

- `HF_ENDPOINT=https://hf-mirror.com` — Required in China for downloading models from HuggingFace. Set before any command that loads Qwen2.5 models or runs fine-tuning.

## Architecture

### Data flow

```
Webcam → YOLO26 pose (17 keypoints) → PoseAnalyzer → ContextEngine → guidance text
                                                      → JointAngleHeatmap → ASCII heatmap
                                User query → FitnessAgent.chat() → Qwen2.5 (+LoRA) → reply
                                UserProfile → PlanGenerator → weekly workout plan
                                AnalysisResult + GuidanceState → RealTimeCoach → DashScope API → chat panel
```

### AI chat dual mode

The chat assistant supports two modes, toggled in the GUI settings panel:

- **Remote API (recommended)** — Calls Alibaba Cloud Bailian (百炼) via OpenAI-compatible endpoint (`dashscope.aliyuncs.com`). Uses a fine-tuned Qwen2.5-7B with LoRA, no local GPU needed. Config: API key + model code in the settings panel, or `data/api_config.example.json` as reference.
- **Local mode** — Loads Qwen2.5 (0.5B–7B) locally via `BaseModel`. Requires `torch` + `transformers`. Falls back to this if remote is unchecked.

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

- **`code/models/fine_tuning/prepare_data.py`** — Converts the pipeline dataset into train/eval JSONL splits (90/10) for the trainer.

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

## Web Frontend (Vue 3 + FastAPI)

### Overview

A modern browser-based UI replacing the Tkinter desktop GUI. Uses Vue 3 + Vite + TypeScript + TailwindCSS for the frontend and FastAPI + WebSocket for the backend. The frontend communicates with the backend via WebSocket (real-time pose detection) and REST API (AI chat).

### Design system

- Background: deep black (`#0a0a0a`)
- Accent gradient: flame orange (`#ff6a00`) → rose (`#ee0979`)
- Glow effects on score thresholds (≥80 strong glow, ≥60 medium, <60 none)
- CSS gauge bars (not SVG) for uniform thickness at any aspect ratio
- Particle background for visual depth

### Web data flow

```
Browser camera (MediaStream API)
  → useCamera.ts captures frames from hidden <video> element
  → base64 JPEG at ~30fps
  → WebSocket /ws/detect
  → backend DetectorService (YOLO26 + PoseAnalyzer + ContextEngine)
  → JSON response {keypoints, score, phase, rep_count, errors, guidance}
  → frontend updates VideoStage, GaugeBars, SkeletonOverlay, ScorePanel

User chat message
  → POST /api/chat {message, history}
  → backend tries remote API (DashScope) first, falls back to local model
  → streaming/complete response returned to AiCoach component
```

### Backend modules (`backend/`)

- **`backend/main.py`** — FastAPI app with CORS middleware. Mounts detect and chat routers.
- **`backend/routers/detect.py`** — WebSocket `/ws/detect` endpoint. Handles `set_exercise`, `reset`, `frame` message types. Lazy-loads DetectorService.
- **`backend/routers/chat.py`** — REST `POST /api/chat`. Tries remote DashScope API first (reads `data/api_config.json`), falls back to local FitnessAgent.
- **`backend/services/detector.py`** — Wraps YOLO26 model + PoseAnalyzer + ContextEngine. `process_frame()` returns detection results dict.
- **`backend/services/agent_service.py`** — Lazy singleton for FitnessAgent. Defers `transformers` import until first chat request.
- **`backend/schemas.py`** — Pydantic models for API request/response types.

### Frontend modules (`frontend/src/`)

- **Composables:**
  - `useCamera.ts` — MediaStream acquisition, hidden video element for frame capture, exposes `stream` ref for display binding
  - `useWebSocket.ts` — WebSocket connection management, reconnection, message parsing. Exposes `connected`, `lastResult`, `sendFrame()`, `setExercise()`, `reset()`
  - `useTrainingState.ts` — State machine (idle/running/paused), elapsed timer with formatted output

- **Components:**
  - `VideoStage.vue` — Main video display with HUD overlays (rep count, phase, timer). Binds camera `stream` via prop watching
  - `GaugeBar.vue` — CSS-based gauge bars (left/right/bottom) showing angle, temporal, symmetry scores
  - `SkeletonOverlay.vue` — Canvas overlay drawing skeleton with gradient bones and glowing joints; error joints highlighted red
  - `ScorePanel.vue` — Right sidebar total score display with ring gauge
  - `CorrectionPanel.vue` — Error list with severity indicators
  - `AiCoach.vue` — Chat interface for AI coaching Q&A
  - `ControlBar.vue` — Exercise selector, start/pause/reset buttons
  - `RingGauge.vue` — SVG circular progress indicator
  - `ParticleBackground.vue` — Animated particle canvas background

- **`App.vue`** — Root component wiring all pieces together. Runs frame capture loop at ~30fps, manages WebSocket lifecycle.

### Key implementation decisions

1. **Lazy-loading for heavy ML dependencies** — All backend imports of `ultralytics`, `transformers`, `torch` are deferred to first use. This allows the FastAPI server to start instantly without loading GB-scale models at import time. Pattern: use `get_detector()` / `get_agent()` factory functions instead of module-level instantiation.

2. **Camera stream separation** — `useCamera.ts` creates a hidden `<video>` element purely for frame extraction (canvas drawImage). The visible video in `VideoStage.vue` receives the `MediaStream` object via a `stream` prop and a `watch()` that sets `video.srcObject`. This avoids conflicts between display and capture.

3. **WebSocket race condition handling** — After calling `ws.connect()`, the frontend polls `ws.connected.value` via `setInterval` before sending the initial `set_exercise` command. This prevents messages from being lost if sent before the WebSocket handshake completes.

4. **CSS gauge bars over SVG arcs** — SVG arcs with `preserveAspectRatio="none"` caused non-uniform stroke width (thin in the middle, thick at ends). CSS `div` elements with `border-radius` and percentage-based `width`/`height` maintain uniform thickness regardless of container aspect ratio.

5. **Remote API fallback for chat** — `backend/routers/chat.py` reads `data/api_config.json` for DashScope credentials. If available, uses the OpenAI-compatible SDK to call the remote fine-tuned Qwen2.5-7B. If unavailable or fails, gracefully falls back to local `FitnessAgent` (which requires `transformers`). This allows the chat feature to work without local GPU.

6. **Error count as computed property** — Initially `totalErrors` was a `ref` that accumulated `errors.length` every frame, causing infinite growth. Fixed by making it a `computed(() => lastResult.value?.errors?.length ?? 0)` that reflects only the current frame's error count.

### Vite proxy configuration (`frontend/vite.config.ts`)

The dev server proxies WebSocket and API requests to the backend:
- `/ws` → `ws://localhost:8000` (WebSocket upgrade)
- `/api` → `http://localhost:8000` (REST)

### Running the full stack

```bash
# Terminal 1: Backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd frontend && npm run dev

# Open http://localhost:5173 in browser
# Grant camera permission when prompted
# Select exercise from dropdown, click "开始训练"
```

### Troubleshooting

- **Port 8000 already in use**: `lsof -ti:8000 | xargs kill -9`
- **"No module named 'backend'"**: Must run `uvicorn backend.main:app` from the project root directory, not from inside `backend/`
- **npm install permission error**: Use `npm install --cache /tmp/npm-cache`
- **WebSocket not connecting through proxy**: Check that system SOCKS proxy isn't intercepting localhost. Use `NO_PROXY=localhost` if needed
- **Camera shows black**: Ensure browser has camera permission and no other app is using the webcam
