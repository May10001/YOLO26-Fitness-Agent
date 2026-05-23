# YOLO26 Web Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vue 3 + FastAPI web frontend for the YOLO26 fitness coaching system with real-time pose detection, scoring gauges, AI chat, and creative visual effects.

**Architecture:** FastAPI backend wraps existing `PoseAnalyzer`, `ContextEngine`, and `FitnessAgent` modules behind WebSocket and REST endpoints. Vue 3 frontend handles camera capture, renders video with Canvas-based skeleton overlay, displays scoring via CSS gauge bars, and provides AI chat. Communication is WebSocket for real-time detection, REST for chat/history.

**Tech Stack:** Vue 3 + Vite + TypeScript + TailwindCSS (frontend), FastAPI + uvicorn + websockets (backend), existing YOLO26 + PoseAnalyzer + FitnessAgent (unchanged)

---

## File Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── types/index.ts
│   ├── assets/styles/
│   │   ├── theme.css
│   │   └── animations.css
│   ├── composables/
│   │   ├── useCamera.ts
│   │   ├── useWebSocket.ts
│   │   └── useTrainingState.ts
│   └── components/
│       ├── ParticleBackground.vue
│       ├── VideoStage.vue
│       ├── GaugeBar.vue
│       ├── SkeletonOverlay.vue
│       ├── ScorePanel.vue
│       ├── CorrectionPanel.vue
│       ├── AiCoach.vue
│       └── ControlBar.vue
backend/
├── main.py
├── schemas.py
├── routers/
│   ├── __init__.py
│   ├── detect.py
│   └── chat.py
└── services/
    ├── __init__.py
    ├── detector.py
    └── agent_service.py
```

---

## Task 1: Backend — Schemas & FastAPI Skeleton

**Files:**
- Create: `backend/main.py`
- Create: `backend/schemas.py`
- Create: `backend/routers/__init__.py`

- [ ] **Step 1: Create backend directory structure**

Run: `mkdir -p backend/routers backend/services && touch backend/__init__.py backend/routers/__init__.py backend/services/__init__.py`

- [ ] **Step 2: Create `backend/schemas.py`**

```python
# backend/schemas.py
from pydantic import BaseModel


class ScoreData(BaseModel):
    total: float
    angle: float
    temporal: float
    symmetry: float


class ErrorData(BaseModel):
    name: str
    severity: int
    message: str
    suggestion: str


class DetectionResult(BaseModel):
    detected: bool
    keypoints: list[list[float]] | None = None
    score: ScoreData | None = None
    phase: str | None = None
    count: int | None = None
    hold_time: float | None = None
    errors: list[ErrorData] | None = None
    guidance: dict | None = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold directory structure and schemas"
```

---

## Task 2: Backend — Detector Service

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/detector.py`

- [ ] **Step 1: Create detector service wrapping PoseAnalyzer**

```python
# backend/services/detector.py
import sys
from pathlib import Path
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.pose_analyzer import PoseAnalyzer, AnalysisResult, EXERCISE_STANDARDS
from code.guidance.context_engine import ContextEngine, GuidanceMessage

EXERCISE_LIST = list(EXERCISE_STANDARDS.keys())


class DetectorService:
    def __init__(self, model_path: str = "yolo26n-pose.pt"):
        self.model = YOLO(model_path)
        self.analyzer: PoseAnalyzer | None = None
        self.context_engine: ContextEngine | None = None
        self.current_exercise: str = "深蹲"

    def set_exercise(self, name: str):
        if name not in EXERCISE_STANDARDS:
            raise ValueError(f"Unsupported exercise: {name}")
        self.current_exercise = name
        self.analyzer = PoseAnalyzer(name)
        self.context_engine = ContextEngine(name)

    def process_frame(self, frame: np.ndarray) -> dict:
        if self.analyzer is None:
            self.set_exercise(self.current_exercise)

        results = self.model(frame, verbose=False)
        if not results or len(results[0].keypoints) == 0:
            return {"detected": False}

        kp_data = results[0].keypoints[0]
        keypoints = kp_data.xy[0].cpu().numpy()
        confidences = kp_data.conf[0].cpu().numpy() if kp_data.conf is not None else None

        analysis = self.analyzer.analyze_frame(keypoints, confidences)

        guidance = None
        if self.context_engine:
            msg = self.context_engine.process(analysis)
            if msg:
                guidance = {"type": msg.type.value, "text": msg.text, "priority": msg.priority}

        return {
            "detected": True,
            "keypoints": keypoints.tolist(),
            "score": {
                "total": analysis.score.total,
                "angle": analysis.score.angle_score,
                "temporal": analysis.score.temporal_score,
                "symmetry": analysis.score.symmetry_score,
            },
            "phase": analysis.phase,
            "count": analysis.count,
            "hold_time": analysis.hold_time,
            "errors": [
                {"name": e.name, "severity": e.severity, "message": e.message, "suggestion": e.suggestion}
                for e in analysis.errors
            ],
            "guidance": guidance,
        }

    def reset(self):
        self.analyzer = PoseAnalyzer(self.current_exercise)
        self.context_engine = ContextEngine(self.current_exercise)
```

- [ ] **Step 2: Create empty `__init__.py`**

```python
# backend/services/__init__.py
```

- [ ] **Step 3: Verify import works**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent && python -c "from backend.services.detector import DetectorService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/
git commit -m "feat(backend): add detector service wrapping PoseAnalyzer"
```

---

## Task 3: Backend — WebSocket Detection Route

**Files:**
- Create: `backend/routers/detect.py`

- [ ] **Step 1: Implement WebSocket endpoint**

```python
# backend/routers/detect.py
import base64
import numpy as np
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.detector import DetectorService

router = APIRouter()
detector = DetectorService()


@router.websocket("/ws/detect")
async def websocket_detect(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()

            if data.get("type") == "set_exercise":
                detector.set_exercise(data["exercise"])
                await ws.send_json({"type": "exercise_set", "exercise": data["exercise"]})
                continue

            if data.get("type") == "reset":
                detector.reset()
                await ws.send_json({"type": "reset_done"})
                continue

            if data.get("type") == "frame":
                img_bytes = base64.b64decode(data["data"])
                nparr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                result = detector.process_frame(frame)
                await ws.send_json({"type": "result", **result})

    except WebSocketDisconnect:
        pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/detect.py
git commit -m "feat(backend): add WebSocket detection route"
```

---

## Task 4: Backend — Chat Route & Agent Service

**Files:**
- Create: `backend/services/agent_service.py`
- Create: `backend/routers/chat.py`

- [ ] **Step 1: Create agent service**

```python
# backend/services/agent_service.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from code.agent import FitnessAgent

_agent: FitnessAgent | None = None


def get_agent() -> FitnessAgent:
    global _agent
    if _agent is None:
        _agent = FitnessAgent(model_size="0.5B")
    return _agent
```

- [ ] **Step 2: Create chat router**

```python
# backend/routers/chat.py
from fastapi import APIRouter
from pydantic import BaseModel

from ..services.agent_service import get_agent
from ..services.detector import EXERCISE_LIST

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    pose_context: str | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    agent = get_agent()
    reply = agent.chat(req.message, pose_context=req.pose_context)
    return ChatResponse(reply=reply)


@router.get("/exercises")
async def list_exercises():
    return {"exercises": EXERCISE_LIST}


@router.post("/session/start")
async def session_start():
    return {"status": "started"}


@router.post("/session/stop")
async def session_stop():
    return {"status": "stopped"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/agent_service.py backend/routers/chat.py
git commit -m "feat(backend): add chat route and agent service"
```

PLACEHOLDER_TASK4_END

---

## Task 5: Backend — Main Entry & CORS

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Wire up FastAPI app with routers and CORS**

```python
# backend/main.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.detect import router as detect_router
from .routers.chat import router as chat_router

app = FastAPI(title="YOLO26 Fitness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detect_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Create `backend/routers/__init__.py`**

```python
# backend/routers/__init__.py
```

- [ ] **Step 3: Create `backend/schemas.py`** (shared Pydantic models)

```python
# backend/schemas.py
from pydantic import BaseModel


class ScoreData(BaseModel):
    total: float
    angle: float
    temporal: float
    symmetry: float


class ErrorData(BaseModel):
    name: str
    severity: int
    message: str
    suggestion: str


class DetectionResult(BaseModel):
    detected: bool
    keypoints: list[list[float]] | None = None
    score: ScoreData | None = None
    phase: str | None = None
    count: int | None = None
    hold_time: float | None = None
    errors: list[ErrorData] | None = None
    guidance: dict | None = None
```

- [ ] **Step 4: Test server starts**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &; sleep 3; curl http://localhost:8000/api/health; kill %1`
Expected: `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): complete FastAPI app with CORS and health check"
```

---

## Task 6: Frontend — Project Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: Initialize Vue 3 + Vite project**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent && npm create vite@latest frontend -- --template vue-ts`

- [ ] **Step 2: Install dependencies**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent/frontend && npm install && npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`

- [ ] **Step 3: Configure tailwind.config.js**

```javascript
// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        flame: '#ff6a00',
        rose: '#ee0979',
        success: '#38ef7d',
        danger: '#ff4d4d',
        dark: {
          900: '#0a0a0a',
          800: '#111111',
          700: '#1a1a1a',
          600: '#2a2a2a',
        },
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 4: Create `frontend/src/assets/styles/theme.css`**

```css
/* frontend/src/assets/styles/theme.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --flame: #ff6a00;
  --rose: #ee0979;
  --success: #38ef7d;
  --danger: #ff4d4d;
  --bg: #0a0a0a;
  --panel: #111111;
}

body {
  background: var(--bg);
  color: #fff;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  margin: 0;
  overflow: hidden;
  height: 100vh;
}

.glow-card {
  border-radius: 14px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(255,106,0,0.08), rgba(238,9,121,0.04));
  border: 1px solid rgba(255,106,0,0.15);
  box-shadow: 0 0 25px rgba(255,106,0,0.06), 0 0 50px rgba(238,9,121,0.03);
}

.glow-card-strong {
  background: linear-gradient(135deg, rgba(255,106,0,0.1), rgba(238,9,121,0.05));
  border: 1px solid rgba(255,106,0,0.2);
  box-shadow: 0 0 30px rgba(255,106,0,0.08), 0 0 60px rgba(238,9,121,0.04);
}

.gradient-text {
  background: linear-gradient(90deg, var(--flame), var(--rose));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.btn-primary {
  background: linear-gradient(135deg, var(--flame), var(--rose));
  border: none;
  color: #fff;
  border-radius: 10px;
  font-weight: 700;
  box-shadow: 0 0 20px rgba(255,106,0,0.3);
  cursor: pointer;
  transition: box-shadow 0.3s, transform 0.2s;
}
.btn-primary:hover {
  box-shadow: 0 0 30px rgba(255,106,0,0.5);
  transform: scale(1.02);
}
```

- [ ] **Step 5: Create `frontend/src/assets/styles/animations.css`**

```css
/* frontend/src/assets/styles/animations.css */
@keyframes float {
  0%, 100% { transform: translateY(0) scale(1); opacity: 0.3; }
  50% { transform: translateY(-30px) scale(1.2); opacity: 0.6; }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

@keyframes pulse-error {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.5); }
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 1; transform: translate(-50%, -50%) scale(1.02); }
}

.animate-float { animation: float 8s infinite ease-in-out; }
.animate-float-fast { animation: float 4s infinite ease-in-out; }
.animate-pulse-joint { animation: pulse 2s infinite; }
.animate-pulse-error { animation: pulse-error 0.6s infinite; }
.animate-breathe { animation: breathe 3s infinite; }
```

- [ ] **Step 6: Update `frontend/src/main.ts`**

```typescript
// frontend/src/main.ts
import { createApp } from 'vue'
import App from './App.vue'
import './assets/styles/theme.css'
import './assets/styles/animations.css'

createApp(App).mount('#app')
```

- [ ] **Step 7: Create minimal `App.vue`**

```vue
<!-- frontend/src/App.vue -->
<template>
  <div class="h-screen w-screen bg-dark-900 p-3 flex gap-3">
    <div class="flex-[2.2] flex flex-col gap-3">
      <div class="flex-1 rounded-2xl bg-dark-800 border border-flame/20 flex items-center justify-center text-dark-600">
        Video Stage
      </div>
      <div class="h-12 rounded-xl bg-white/[0.02] border border-white/[0.05] flex items-center px-4 text-sm text-gray-500">
        Control Bar
      </div>
    </div>
    <div class="flex-1 max-w-[360px] flex flex-col gap-3">
      <div class="glow-card-strong">Score Panel</div>
      <div class="glow-card">Correction Panel</div>
      <div class="glow-card flex-1">AI Coach</div>
    </div>
  </div>
</template>
```

- [ ] **Step 8: Verify dev server starts**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent/frontend && npm run dev`
Expected: Vite dev server starts, page shows layout skeleton at `http://localhost:5173`

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vue 3 + Vite + TailwindCSS project"
```

---

## Task 7: Frontend — Types & Composables

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/composables/useCamera.ts`
- Create: `frontend/src/composables/useWebSocket.ts`
- Create: `frontend/src/composables/useTrainingState.ts`

- [ ] **Step 1: Define TypeScript types**

```typescript
// frontend/src/types/index.ts
export interface ScoreData {
  total: number
  angle: number
  temporal: number
  symmetry: number
}

export interface ErrorData {
  name: string
  severity: number
  message: string
  suggestion: string
}

export interface GuidanceData {
  type: string
  text: string
  priority: number
}

export interface DetectionResult {
  detected: boolean
  keypoints?: number[][]
  score?: ScoreData
  phase?: string
  count?: number
  hold_time?: number
  errors?: ErrorData[]
  guidance?: GuidanceData
}

export type TrainingState = 'idle' | 'running' | 'paused'
```

- [ ] **Step 2: Create `useCamera` composable**

```typescript
// frontend/src/composables/useCamera.ts
import { ref, onUnmounted } from 'vue'

export function useCamera() {
  const videoRef = ref<HTMLVideoElement | null>(null)
  const stream = ref<MediaStream | null>(null)
  const isActive = ref(false)

  async function start() {
    const s = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: 'user' }
    })
    stream.value = s
    if (videoRef.value) {
      videoRef.value.srcObject = s
      await videoRef.value.play()
    }
    isActive.value = true
  }

  function stop() {
    stream.value?.getTracks().forEach(t => t.stop())
    stream.value = null
    isActive.value = false
  }

  function captureFrame(): string | null {
    if (!videoRef.value || !isActive.value) return null
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.value.videoWidth
    canvas.height = videoRef.value.videoHeight
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(videoRef.value, 0, 0)
    return canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
  }

  onUnmounted(stop)

  return { videoRef, isActive, start, stop, captureFrame }
}
```

- [ ] **Step 3: Create `useWebSocket` composable**

```typescript
// frontend/src/composables/useWebSocket.ts
import { ref } from 'vue'
import type { DetectionResult } from '../types'

export function useWebSocket(url: string = 'ws://localhost:8000/ws/detect') {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const lastResult = ref<DetectionResult | null>(null)

  function connect() {
    ws.value = new WebSocket(url)
    ws.value.onopen = () => { connected.value = true }
    ws.value.onclose = () => { connected.value = false }
    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'result') {
        lastResult.value = data as DetectionResult
      }
    }
  }

  function sendFrame(base64Data: string) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'frame', data: base64Data }))
    }
  }

  function setExercise(name: string) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'set_exercise', exercise: name }))
    }
  }

  function reset() {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'reset' }))
    }
  }

  function disconnect() {
    ws.value?.close()
    ws.value = null
    connected.value = false
  }

  return { connected, lastResult, connect, sendFrame, setExercise, reset, disconnect }
}
```

- [ ] **Step 4: Create `useTrainingState` composable**

```typescript
// frontend/src/composables/useTrainingState.ts
import { ref, computed } from 'vue'
import type { TrainingState } from '../types'

export function useTrainingState() {
  const state = ref<TrainingState>('idle')
  const startTime = ref<number>(0)
  const elapsed = ref<number>(0)
  let timer: number | null = null

  const isRunning = computed(() => state.value === 'running')
  const isIdle = computed(() => state.value === 'idle')

  function start() {
    state.value = 'running'
    startTime.value = Date.now()
    timer = window.setInterval(() => {
      elapsed.value = Math.floor((Date.now() - startTime.value) / 1000)
    }, 1000)
  }

  function pause() {
    state.value = 'paused'
    if (timer) clearInterval(timer)
  }

  function resume() {
    state.value = 'running'
    startTime.value = Date.now() - elapsed.value * 1000
    timer = window.setInterval(() => {
      elapsed.value = Math.floor((Date.now() - startTime.value) / 1000)
    }, 1000)
  }

  function stop() {
    state.value = 'idle'
    elapsed.value = 0
    if (timer) clearInterval(timer)
  }

  const formattedTime = computed(() => {
    const m = Math.floor(elapsed.value / 60)
    const s = elapsed.value % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  })

  return { state, isRunning, isIdle, elapsed, formattedTime, start, pause, resume, stop }
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/ frontend/src/composables/
git commit -m "feat(frontend): add types and composables (camera, websocket, training state)"
```

PLACEHOLDER_TASK7_END

---

## Task 8: Frontend — ParticleBackground Component

**Files:**
- Create: `frontend/src/components/ParticleBackground.vue`

- [ ] **Step 1: Create particle background component**

```vue
<!-- frontend/src/components/ParticleBackground.vue -->
<template>
  <div class="fixed inset-0 z-0 pointer-events-none">
    <div
      v-for="p in particles"
      :key="p.id"
      class="absolute rounded-full"
      :class="isTraining ? 'animate-float-fast' : 'animate-float'"
      :style="{
        width: p.size + 'px',
        height: p.size + 'px',
        background: p.color,
        top: p.top + '%',
        left: p.left + '%',
        animationDelay: p.delay + 's',
      }"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{ isTraining: boolean }>()

const particles = [
  { id: 1, size: 4, color: 'rgba(255,106,0,0.4)', top: 20, left: 15, delay: 0 },
  { id: 2, size: 3, color: 'rgba(238,9,121,0.3)', top: 60, left: 25, delay: 2 },
  { id: 3, size: 5, color: 'rgba(255,106,0,0.3)', top: 30, left: 75, delay: 4 },
  { id: 4, size: 3, color: 'rgba(238,9,121,0.4)', top: 70, left: 85, delay: 1 },
  { id: 5, size: 4, color: 'rgba(255,106,0,0.3)', top: 80, left: 45, delay: 3 },
  { id: 6, size: 6, color: 'rgba(238,9,121,0.2)', top: 10, left: 55, delay: 5 },
  { id: 7, size: 3, color: 'rgba(255,106,0,0.5)', top: 45, left: 90, delay: 6 },
]
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ParticleBackground.vue
git commit -m "feat(frontend): add particle background component"
```

---

## Task 9: Frontend — GaugeBar Component

**Files:**
- Create: `frontend/src/components/GaugeBar.vue`

- [ ] **Step 1: Create gauge bar component**

```vue
<!-- frontend/src/components/GaugeBar.vue -->
<template>
  <div class="absolute rounded-md" :style="trackStyle" />
  <div class="absolute rounded-md transition-all duration-700" :style="valueStyle" />
  <div class="absolute text-[10px] font-semibold" :style="labelStyle">
    <span :style="{ color: labelColor }">{{ label }}</span>
    <span class="text-gray-500 ml-1 text-[9px]">{{ value }}/{{ max }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  direction: 'left' | 'right' | 'bottom'
  value: number
  max: number
  label: string
  labelColor?: string
}>()

const ratio = computed(() => Math.min(props.value / props.max, 1))

const trackStyle = computed(() => {
  const base = { background: 'rgba(255,255,255,0.06)' }
  if (props.direction === 'left') return { ...base, left: '10px', top: '50px', bottom: '50px', width: '10px' }
  if (props.direction === 'right') return { ...base, right: '10px', top: '50px', bottom: '50px', width: '10px' }
  return { ...base, left: '50px', right: '50px', bottom: '10px', height: '10px' }
})

const gradients: Record<string, string> = {
  left: 'linear-gradient(180deg, #ff6a00, #ee0979)',
  right: 'linear-gradient(180deg, #ee0979, #ff6a00)',
  bottom: 'linear-gradient(90deg, #ff6a00, #ee0979)',
}

const valueStyle = computed(() => {
  const glow = '0 0 14px rgba(255,106,0,0.5), 0 0 28px rgba(238,9,121,0.2)'
  if (props.direction === 'left') {
    return { left: '10px', top: '50px', width: '10px', height: `calc((100% - 100px) * ${ratio.value})`, background: gradients.left, boxShadow: glow }
  }
  if (props.direction === 'right') {
    return { right: '10px', top: '50px', width: '10px', height: `calc((100% - 100px) * ${ratio.value})`, background: gradients.right, boxShadow: glow }
  }
  return { left: '50px', bottom: '10px', height: '10px', width: `calc((100% - 100px) * ${ratio.value})`, background: gradients.bottom, boxShadow: glow }
})

const labelStyle = computed(() => {
  if (props.direction === 'left') return { left: '26px', top: '38px' }
  if (props.direction === 'right') return { right: '26px', top: '38px', textAlign: 'right' }
  return { left: '30px', bottom: '26px' }
})

const labelColor = computed(() => props.labelColor || '#ff6a00')
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/GaugeBar.vue
git commit -m "feat(frontend): add GaugeBar component"
```

---

## Task 10: Frontend — SkeletonOverlay Component

**Files:**
- Create: `frontend/src/components/SkeletonOverlay.vue`

- [ ] **Step 1: Create skeleton overlay with Canvas**

```vue
<!-- frontend/src/components/SkeletonOverlay.vue -->
<template>
  <canvas ref="canvasRef" class="absolute inset-0 w-full h-full pointer-events-none" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import type { ErrorData } from '../types'

const props = defineProps<{
  keypoints: number[][] | null
  errors: ErrorData[]
  videoWidth: number
  videoHeight: number
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)

const SKELETON = [
  [5,7],[7,9],[6,8],[8,10],[5,6],[5,11],[6,12],
  [11,12],[11,13],[13,15],[12,14],[14,16],[0,1],[0,2],[1,3],[2,4]
]

const ERROR_JOINTS = new Set([13, 14, 15, 16])

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !props.keypoints) return
  const ctx = canvas.getContext('2d')!
  canvas.width = canvas.clientWidth
  canvas.height = canvas.clientHeight

  const scaleX = canvas.width / props.videoWidth
  const scaleY = canvas.height / props.videoHeight

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Draw bones
  ctx.lineWidth = 2
  for (const [i, j] of SKELETON) {
    const [x1, y1] = props.keypoints[i]
    const [x2, y2] = props.keypoints[j]
    if (x1 === 0 && y1 === 0) continue
    if (x2 === 0 && y2 === 0) continue

    const gradient = ctx.createLinearGradient(x1*scaleX, y1*scaleY, x2*scaleX, y2*scaleY)
    gradient.addColorStop(0, 'rgba(255,106,0,0.7)')
    gradient.addColorStop(1, 'rgba(238,9,121,0.5)')
    ctx.strokeStyle = gradient
    ctx.shadowColor = 'rgba(255,106,0,0.3)'
    ctx.shadowBlur = 6
    ctx.beginPath()
    ctx.moveTo(x1 * scaleX, y1 * scaleY)
    ctx.lineTo(x2 * scaleX, y2 * scaleY)
    ctx.stroke()
  }

  // Draw joints
  const hasKneeError = props.errors.some(e => e.name.includes('膝盖'))
  for (let i = 0; i < props.keypoints.length; i++) {
    const [x, y] = props.keypoints[i]
    if (x === 0 && y === 0) continue

    const isError = hasKneeError && ERROR_JOINTS.has(i)
    const color = isError ? '#ff4d4d' : '#ff6a00'
    const radius = isError ? 7 : 5

    ctx.shadowColor = color
    ctx.shadowBlur = isError ? 16 : 10
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(x * scaleX, y * scaleY, radius, 0, Math.PI * 2)
    ctx.fill()
  }

  ctx.shadowBlur = 0
}

watch(() => props.keypoints, draw)
onMounted(draw)
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SkeletonOverlay.vue
git commit -m "feat(frontend): add SkeletonOverlay canvas component"
```

---

## Task 11: Frontend — VideoStage Component

**Files:**
- Create: `frontend/src/components/VideoStage.vue`

- [ ] **Step 1: Create video stage with HUD and gauges**

```vue
<!-- frontend/src/components/VideoStage.vue -->
<template>
  <div class="flex-1 rounded-2xl overflow-hidden relative transition-all duration-700"
       :class="glowClass">
    <!-- Video element -->
    <video ref="videoRef" class="w-full h-full object-cover" muted playsinline />

    <!-- Skeleton overlay -->
    <SkeletonOverlay
      v-if="result?.keypoints"
      :keypoints="result.keypoints"
      :errors="result.errors || []"
      :video-width="640"
      :video-height="480"
    />

    <!-- Gauge bars -->
    <GaugeBar direction="left" :value="score.angle" :max="40" label="角度" label-color="#ff6a00" />
    <GaugeBar direction="right" :value="score.symmetry" :max="30" label="对称" label-color="#ee0979" />
    <GaugeBar direction="bottom" :value="score.temporal" :max="30" label="时序" label-color="#ff6a00" />

    <!-- HUD top -->
    <div class="absolute top-3.5 left-7 flex gap-2 items-center">
      <span v-if="isRunning" class="px-2.5 py-1 rounded-full text-[10px] font-bold text-white bg-gradient-to-r from-flame to-rose shadow-[0_0_12px_rgba(255,106,0,0.4)]">REC</span>
      <span class="px-2.5 py-1 rounded-full text-[10px] text-gray-300 bg-black/60 backdrop-blur border border-white/10">{{ exercise }}</span>
      <span v-if="result?.phase" class="px-2.5 py-1 rounded-full text-[10px] text-emerald-400 bg-black/60 backdrop-blur border border-emerald-500/30">{{ result.phase }}</span>
    </div>

    <!-- HUD bottom-left stats -->
    <div class="absolute bottom-[46px] left-7 flex gap-1.5">
      <span class="px-2.5 py-1 rounded-lg text-[10px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">次数 <b class="text-flame">{{ result?.count || 0 }}</b></span>
      <span class="px-2.5 py-1 rounded-lg text-[10px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">时长 <b class="text-flame">{{ formattedTime }}</b></span>
      <span class="px-2.5 py-1 rounded-lg text-[10px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">FPS <b class="text-flame">{{ fps }}</b></span>
    </div>

    <!-- HUD bottom-right score -->
    <div class="absolute bottom-7 right-7 bg-black/75 backdrop-blur-lg border border-flame/25 rounded-xl px-4 py-2 text-center">
      <div class="text-3xl font-extrabold gradient-text leading-none">{{ score.total.toFixed(0) }}</div>
      <div class="text-[9px] text-gray-500 mt-0.5">TOTAL</div>
    </div>

    <!-- Ready state overlay -->
    <div v-if="!isRunning" class="absolute top-1/2 left-1/2 animate-breathe text-[11px] text-flame uppercase tracking-[3px] px-7 py-3 border border-flame/30 rounded-full bg-black/70 backdrop-blur">
      READY — 点击开始训练
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DetectionResult, ScoreData } from '../types'
import GaugeBar from './GaugeBar.vue'
import SkeletonOverlay from './SkeletonOverlay.vue'

const props = defineProps<{
  videoRef: HTMLVideoElement | null
  result: DetectionResult | null
  exercise: string
  isRunning: boolean
  formattedTime: string
  fps: number
}>()

const score = computed<ScoreData>(() => props.result?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 })

const glowClass = computed(() => {
  const total = score.value.total
  if (total >= 80) return 'border border-flame/30 shadow-[0_0_60px_rgba(255,106,0,0.12)]'
  if (total >= 60) return 'border border-flame/15 shadow-[0_0_30px_rgba(255,106,0,0.06)]'
  return 'border border-white/10 shadow-none'
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/VideoStage.vue
git commit -m "feat(frontend): add VideoStage component with HUD and gauges"
```

PLACEHOLDER_TASK11_END

---

## Task 12: Frontend — ScorePanel, CorrectionPanel, AiCoach, ControlBar

**Files:**
- Create: `frontend/src/components/ScorePanel.vue`
- Create: `frontend/src/components/CorrectionPanel.vue`
- Create: `frontend/src/components/AiCoach.vue`
- Create: `frontend/src/components/ControlBar.vue`

- [ ] **Step 1: Create ScorePanel**

```vue
<!-- frontend/src/components/ScorePanel.vue -->
<template>
  <div class="glow-card-strong rounded-[14px] p-4">
    <div class="flex justify-between items-center mb-3">
      <span class="text-[10px] uppercase tracking-wider text-flame/80 font-semibold">Score Detail</span>
      <span class="text-[10px] text-gray-600">第 {{ count }} 次</span>
    </div>
    <!-- Ring gauges -->
    <div class="flex gap-3 justify-center mb-3">
      <RingGauge :value="score.angle" :max="40" label="角度" color="#ff6a00" />
      <RingGauge :value="score.temporal" :max="30" label="时序" color="#ee0979" />
      <RingGauge :value="score.symmetry" :max="30" label="对称" color="#ff6a00" />
    </div>
    <!-- Stats grid -->
    <div class="grid grid-cols-3 gap-1.5">
      <div class="bg-white/[0.03] rounded-lg p-2 text-center border border-white/[0.04]">
        <div class="text-base font-bold">{{ count }}</div>
        <div class="text-[8px] text-gray-500">总次数</div>
      </div>
      <div class="bg-white/[0.03] rounded-lg p-2 text-center border border-white/[0.04]">
        <div class="text-base font-bold">{{ formattedTime }}</div>
        <div class="text-[8px] text-gray-500">训练时长</div>
      </div>
      <div class="bg-white/[0.03] rounded-lg p-2 text-center border border-white/[0.04]">
        <div class="text-base font-bold text-danger">{{ errorCount }}</div>
        <div class="text-[8px] text-gray-500">错误次数</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ScoreData } from '../types'
import RingGauge from './RingGauge.vue'

defineProps<{
  score: ScoreData
  count: number
  formattedTime: string
  errorCount: number
}>()
</script>
```

- [ ] **Step 2: Create RingGauge helper component**

Create `frontend/src/components/RingGauge.vue`:

```vue
<!-- frontend/src/components/RingGauge.vue -->
<template>
  <div class="text-center">
    <svg width="58" height="58" viewBox="0 0 58 58">
      <circle cx="29" cy="29" r="23" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
      <circle cx="29" cy="29" r="23" fill="none" :stroke="color" stroke-width="5"
        stroke-linecap="round" :stroke-dasharray="circumference"
        :stroke-dashoffset="offset" transform="rotate(-90 29 29)"
        :style="{ filter: `drop-shadow(0 0 4px ${color}80)` }" />
      <text x="29" y="33" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">{{ value }}</text>
    </svg>
    <div class="text-[9px] text-gray-500 mt-0.5">{{ label }} /{{ max }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: number; max: number; label: string; color: string }>()

const circumference = 2 * Math.PI * 23
const offset = computed(() => circumference * (1 - Math.min(props.value / props.max, 1)))
</script>
```

- [ ] **Step 3: Create CorrectionPanel**

```vue
<!-- frontend/src/components/CorrectionPanel.vue -->
<template>
  <div class="glow-card rounded-[14px] p-3.5">
    <div class="text-[10px] uppercase tracking-wider text-flame/70 font-semibold mb-2.5">Correction</div>
    <div v-if="errors.length === 0 && !positiveMsg" class="text-[10px] text-gray-600">暂无纠错信息</div>
    <div v-for="err in errors" :key="err.name"
         class="flex items-start gap-2.5 p-2.5 rounded-lg bg-danger/[0.06] border border-danger/[0.15] mb-1.5">
      <div class="w-2 h-2 rounded-full bg-danger shadow-[0_0_10px_rgba(255,77,77,0.6)] mt-[3px] shrink-0" />
      <div>
        <div class="text-[11px] text-gray-100 font-medium">{{ err.name }}</div>
        <div class="text-[10px] text-gray-500 mt-0.5">{{ err.suggestion }}</div>
      </div>
    </div>
    <div v-if="positiveMsg"
         class="flex items-start gap-2.5 p-2.5 rounded-lg bg-success/[0.04] border border-success/[0.12]">
      <div class="w-2 h-2 rounded-full bg-success shadow-[0_0_8px_rgba(56,239,125,0.5)] mt-[3px] shrink-0" />
      <div>
        <div class="text-[11px] text-gray-100 font-medium">动作良好</div>
        <div class="text-[10px] text-gray-500 mt-0.5">{{ positiveMsg }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ErrorData, ScoreData } from '../types'

const props = defineProps<{ errors: ErrorData[]; score: ScoreData }>()

const positiveMsg = computed(() => {
  if (props.errors.length === 0 && props.score.total >= 80) return '继续保持当前动作质量'
  return null
})
</script>
```

- [ ] **Step 4: Create AiCoach**

```vue
<!-- frontend/src/components/AiCoach.vue -->
<template>
  <div class="glow-card rounded-[14px] p-3.5 flex-1 flex flex-col min-h-0">
    <div class="text-[10px] uppercase tracking-wider text-flame/70 font-semibold mb-2">AI Coach</div>
    <div ref="messagesRef" class="flex-1 overflow-y-auto flex flex-col gap-1.5 pb-2">
      <div v-for="(msg, i) in messages" :key="i"
           class="max-w-[92%] rounded-lg px-3 py-2 text-[10px]"
           :class="msg.role === 'ai'
             ? 'bg-flame/[0.08] border border-flame/[0.12] text-gray-200 self-start'
             : 'bg-white/[0.05] border border-white/[0.08] text-gray-400 self-end'">
        {{ msg.text }}
      </div>
    </div>
    <div class="flex gap-1.5 mt-2">
      <input v-model="input" @keyup.enter="send"
             class="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[10px] text-white outline-none"
             placeholder="问问AI教练..." />
      <button @click="send" class="btn-primary w-8 h-8 rounded-lg text-xs flex items-center justify-center">→</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'

interface Message { role: 'ai' | 'user'; text: string }

const messages = ref<Message[]>([
  { role: 'ai', text: '你好！我是你的AI健身教练，有什么可以帮你的？' }
])
const input = ref('')
const messagesRef = ref<HTMLElement | null>(null)

async function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', text })
  input.value = ''
  await nextTick()
  scrollToBottom()

  try {
    const res = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    })
    const data = await res.json()
    messages.value.push({ role: 'ai', text: data.reply })
  } catch {
    messages.value.push({ role: 'ai', text: '连接失败，请检查后端服务是否启动。' })
  }
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
}
</script>
```

- [ ] **Step 5: Create ControlBar**

```vue
<!-- frontend/src/components/ControlBar.vue -->
<template>
  <div class="h-12 rounded-xl bg-white/[0.02] border border-white/[0.05] flex items-center gap-2 px-3.5">
    <button v-if="isIdle" @click="$emit('start')" class="btn-primary px-5 py-2 text-[11px]">开始训练</button>
    <template v-else>
      <button @click="$emit('stop')" class="px-4 py-2 rounded-lg text-[11px] font-semibold bg-danger/[0.12] border border-danger/[0.25] text-danger">停止</button>
      <button @click="$emit('pause')" class="px-4 py-2 rounded-lg text-[11px] bg-white/[0.06] border border-white/10 text-gray-400">
        {{ isPaused ? '继续' : '暂停' }}
      </button>
    </template>
    <div class="flex gap-1.5 ml-auto">
      <button v-for="ex in exercises" :key="ex" @click="$emit('exercise', ex)"
              class="px-2.5 py-1 rounded-lg text-[10px] border transition-colors"
              :class="ex === current
                ? 'bg-gradient-to-r from-flame/20 to-rose/10 border-flame/30 text-flame font-semibold'
                : 'border-white/[0.07] text-gray-600'">
        {{ ex }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  isIdle: boolean
  isPaused: boolean
  current: string
  exercises: string[]
}>()

defineEmits<{
  start: []
  stop: []
  pause: []
  exercise: [name: string]
}>()
</script>
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ScorePanel.vue frontend/src/components/RingGauge.vue frontend/src/components/CorrectionPanel.vue frontend/src/components/AiCoach.vue frontend/src/components/ControlBar.vue
git commit -m "feat(frontend): add ScorePanel, CorrectionPanel, AiCoach, ControlBar components"
```

---

## Task 13: Frontend — Wire Up App.vue

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Replace App.vue with full wired-up layout**

```vue
<!-- frontend/src/App.vue -->
<template>
  <ParticleBackground :is-training="training.isRunning.value" />
  <div class="relative z-10 h-screen w-screen p-3 flex gap-3">
    <!-- Left: Video + Controls -->
    <div class="flex-[2.2] flex flex-col gap-3">
      <VideoStage
        :video-ref="camera.videoRef.value"
        :result="ws.lastResult.value"
        :exercise="currentExercise"
        :is-running="training.isRunning.value"
        :formatted-time="training.formattedTime.value"
        :fps="fps"
      />
      <ControlBar
        :is-idle="training.isIdle.value"
        :is-paused="training.state.value === 'paused'"
        :current="currentExercise"
        :exercises="exercises"
        @start="startTraining"
        @stop="stopTraining"
        @pause="togglePause"
        @exercise="switchExercise"
      />
    </div>
    <!-- Right: Panels -->
    <div class="flex-1 max-w-[360px] flex flex-col gap-2.5">
      <ScorePanel
        :score="currentScore"
        :count="ws.lastResult.value?.count || 0"
        :formatted-time="training.formattedTime.value"
        :error-count="totalErrors"
      />
      <CorrectionPanel
        :errors="ws.lastResult.value?.errors || []"
        :score="currentScore"
      />
      <AiCoach />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { ScoreData } from './types'
import { useCamera } from './composables/useCamera'
import { useWebSocket } from './composables/useWebSocket'
import { useTrainingState } from './composables/useTrainingState'
import ParticleBackground from './components/ParticleBackground.vue'
import VideoStage from './components/VideoStage.vue'
import ControlBar from './components/ControlBar.vue'
import ScorePanel from './components/ScorePanel.vue'
import CorrectionPanel from './components/CorrectionPanel.vue'
import AiCoach from './components/AiCoach.vue'

const camera = useCamera()
const ws = useWebSocket()
const training = useTrainingState()

const exercises = ['深蹲', '俯卧撑', '平板支撑', '卷腹', '开合跳']
const currentExercise = ref('深蹲')
const totalErrors = ref(0)
const fps = ref(0)
let frameInterval: number | null = null
let frameCount = 0
let fpsTimer: number | null = null

const currentScore = computed<ScoreData>(() =>
  ws.lastResult.value?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 }
)

async function startTraining() {
  await camera.start()
  ws.connect()
  ws.setExercise(currentExercise.value)
  training.start()
  totalErrors.value = 0
  startFrameLoop()
}

function stopTraining() {
  stopFrameLoop()
  training.stop()
  camera.stop()
  ws.disconnect()
}

function togglePause() {
  if (training.state.value === 'paused') {
    training.resume()
    startFrameLoop()
  } else {
    training.pause()
    stopFrameLoop()
  }
}

function switchExercise(name: string) {
  currentExercise.value = name
  ws.setExercise(name)
  ws.reset()
  totalErrors.value = 0
}

function startFrameLoop() {
  frameInterval = window.setInterval(() => {
    const frame = camera.captureFrame()
    if (frame) {
      ws.sendFrame(frame)
      frameCount++
    }
    if (ws.lastResult.value?.errors?.length) {
      totalErrors.value += ws.lastResult.value.errors.length
    }
  }, 33) // ~30fps
  fpsTimer = window.setInterval(() => {
    fps.value = frameCount
    frameCount = 0
  }, 1000)
}

function stopFrameLoop() {
  if (frameInterval) clearInterval(frameInterval)
  if (fpsTimer) clearInterval(fpsTimer)
}

onUnmounted(() => {
  stopFrameLoop()
  camera.stop()
  ws.disconnect()
})
</script>
```

- [ ] **Step 2: Verify the app compiles**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent/frontend && npx vue-tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(frontend): wire up App.vue with all components and composables"
```

---

## Task 14: Integration — Run Full Stack

- [ ] **Step 1: Install backend dependencies**

Run: `pip install fastapi uvicorn python-multipart websockets`

- [ ] **Step 2: Start backend**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
Expected: Server starts on port 8000

- [ ] **Step 3: Start frontend**

Run: `cd /Users/may/Documents/Academic/深度学习/YOLO26-Fitness-Agent/frontend && npm run dev`
Expected: Vite dev server on port 5173

- [ ] **Step 4: Test in browser**

Open `http://localhost:5173`:
- Verify layout renders (dark background, particle effects, left/right panels)
- Click "开始训练" → camera permission prompt → video appears
- Gauge bars fill as detection results come in
- Skeleton overlay draws on video
- AI Coach chat sends and receives messages

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete web frontend integration with FastAPI backend"
```
