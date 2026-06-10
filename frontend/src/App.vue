<template>
  <EntryScreen v-if="showEntry" @enter="showEntry = false" />
  <ParticleBackground :is-training="training.isRunning.value" />
  <div class="relative z-10 h-screen w-screen p-3 flex gap-3">
    <div class="flex-[2.2] flex flex-col gap-3">
      <VideoStage
        :result="ws.lastResult.value"
        :guidance="ws.lastGuidance.value"
        :exercise="currentExercise"
        :is-running="training.isRunning.value"
        :formatted-time="training.formattedTime.value"
        :fps="fps"
        :stream="camera.stream.value"
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
    <div class="flex-1 max-w-[360px] flex flex-col gap-2.5">
      <ScorePanel
        :score="currentScore"
        :count="ws.lastResult.value?.count || 0"
        :hold-time="ws.lastResult.value?.hold_time || 0"
        :formatted-time="training.formattedTime.value"
        :error-count="totalErrors"
        :exercise="currentExercise"
      />
      <JointHeatmap
        :joints="ws.lastResult.value?.heatmap?.joints || null"
      />
      <CorrectionPanel
        :errors="ws.lastResult.value?.errors || []"
        :score="currentScore"
      />

      <!-- Tab switcher -->
      <div class="flex gap-1 bg-white/[0.03] rounded-lg p-0.5">
        <button v-for="tab in tabs" :key="tab.key"
                class="flex-1 text-[10px] py-1.5 rounded-md font-medium transition-colors"
                :class="activeTab === tab.key
                  ? 'bg-flame/20 text-flame'
                  : 'text-gray-500 hover:text-gray-300'"
                @click="activeTab = tab.key">
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab content -->
      <AiCoach v-if="activeTab === 'coach'"
               :pose-context="poseContext"
               :coach-message="ws.lastCoachMessage.value" />
      <HistoryPanel v-else-if="activeTab === 'history'" />
      <PlanPanel v-else-if="activeTab === 'plan'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { ScoreData, PoseContext } from './types'
import { useCamera } from './composables/useCamera'
import { useWebSocket } from './composables/useWebSocket'
import { useTrainingState } from './composables/useTrainingState'
import ParticleBackground from './components/ParticleBackground.vue'
import EntryScreen from './components/EntryScreen.vue'
import VideoStage from './components/VideoStage.vue'
import ControlBar from './components/ControlBar.vue'
import ScorePanel from './components/ScorePanel.vue'
import CorrectionPanel from './components/CorrectionPanel.vue'
import AiCoach from './components/AiCoach.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import PlanPanel from './components/PlanPanel.vue'
import JointHeatmap from './components/JointHeatmap.vue'

const camera = useCamera()
const ws = useWebSocket()
const training = useTrainingState()

// Entry screen — shown on load, dismissed on click-to-enter
const showEntry = ref(true)

// Tab state
const tabs = [
  { key: 'coach', label: 'AI教练' },
  { key: 'history', label: '历史' },
  { key: 'plan', label: '计划' },
]
const activeTab = ref('coach')

// Fallback list while fetching from backend
const exercises = ref<string[]>(['深蹲', '俯卧撑', '平板支撑', '卷腹', '开合跳'])
const currentExercise = ref('深蹲')
const fps = ref(0)
let frameInterval: number | null = null
let frameCount = 0
let fpsTimer: number | null = null

// Session tracking
const sessionId = ref<string | null>(null)
const sessionStartTime = ref(0)

// Session-level score tracking
const bestScore = ref(0)
const recentScores = ref<number[]>([])

const currentScore = computed<ScoreData>(() =>
  ws.lastResult.value?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 }
)

const totalErrors = computed(() => {
  return ws.lastResult.value?.errors?.length || 0
})

// Build pose context for AI coach — aggregates latest frame + session stats
const poseContext = computed<PoseContext>(() => {
  const r = ws.lastResult.value
  return {
    exercise_name: currentExercise.value,
    score: r?.score,
    phase: r?.phase,
    rep_count: r?.count ?? 0,
    hold_time: r?.hold_time ?? 0,
    errors: r?.errors,
    best_score: bestScore.value,
    recent_scores: [...recentScores.value],
    chat_mode: 'reactive',
  }
})

// Update session stats whenever a new score arrives
watch(() => ws.lastResult.value?.score?.total, (newTotal) => {
  if (newTotal !== undefined && newTotal > 0) {
    if (newTotal > bestScore.value) bestScore.value = newTotal
    recentScores.value.push(newTotal)
    if (recentScores.value.length > 10) recentScores.value.shift()
  }
})

// Fetch authoritative exercise list from backend
async function fetchExercises() {
  try {
    const res = await fetch('http://localhost:8000/api/exercises')
    if (!res.ok) return
    const data = await res.json()
    if (data.exercises && Array.isArray(data.exercises) && data.exercises.length > 0) {
      exercises.value = data.exercises
      if (!data.exercises.includes(currentExercise.value)) {
        currentExercise.value = data.exercises[0]
      }
    }
  } catch {
    // Keep the hardcoded fallback list
  }
}

onMounted(fetchExercises)

function resetSessionStats() {
  bestScore.value = 0
  recentScores.value = []
}

// ---- Session lifecycle (for training history) ----
async function beginSession() {
  try {
    const res = await fetch('http://localhost:8000/api/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise: currentExercise.value }),
    })
    const data = await res.json()
    sessionId.value = data.session_id || null
    sessionStartTime.value = Date.now()
  } catch { /* non-critical */ }
}

async function endSession() {
  if (!sessionId.value) return
  try {
    const duration = (Date.now() - sessionStartTime.value) / 1000
    await fetch('http://localhost:8000/api/session/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        duration_seconds: duration,
        stats: {
          total_reps: ws.lastResult.value?.count || 0,
          best_score: bestScore.value,
          avg_score: recentScores.value.length > 0
            ? recentScores.value.reduce((a, b) => a + b, 0) / recentScores.value.length
            : 0,
          error_counts: {},  // populated by backend from detector
        },
      }),
    })
  } catch { /* non-critical */ }
  sessionId.value = null
}

async function startTraining() {
  await camera.start()
  ws.connect()
  training.start()
  resetSessionStats()
  await beginSession()
  const waitOpen = setInterval(() => {
    if (ws.connected.value) {
      clearInterval(waitOpen)
      ws.setExercise(currentExercise.value)
      startFrameLoop()
    }
  }, 100)
}

async function stopTraining() {
  stopFrameLoop()
  await endSession()
  training.stop()
  camera.stop()
  ws.disconnect()
  resetSessionStats()
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
  resetSessionStats()
}

function startFrameLoop() {
  frameInterval = window.setInterval(() => {
    const frame = camera.captureFrame()
    if (frame) {
      ws.sendFrame(frame)
      frameCount++
    }
  }, 33)
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
