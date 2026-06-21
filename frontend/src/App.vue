<template>
  <EntryScreen v-if="showEntry" @enter="showEntry = false" />
  <ParticleBackground :is-training="training.isRunning.value" />
  <div class="relative z-10 h-screen w-screen p-3 flex gap-3">
    <div class="flex-[2.2] flex flex-col gap-3">
      <div class="flex-[3] flex gap-3 relative">
        <VideoStage
          class="flex-1"
          :result="ws.lastResult.value"
          :guidance="ws.lastGuidance.value"
          :exercise="currentExercise"
          :is-running="training.isRunning.value"
          :formatted-time="training.formattedTime.value"
          :fps="fps"
          :stream="camera.stream.value"
          :show-debug="showDebug"
          :target-reps="targetReps"
        />
        <PoseViewer
          class="flex-1"
          :keypoints="ws.lastResult.value?.keypoints || null"
          :errors="ws.lastResult.value?.errors || []"
          :score-total="currentScore.total"
        />
        <!-- Debug toggle button -->
        <button
          class="absolute top-6 right-8 z-30 px-2.5 py-1 rounded-full text-[9px] font-bold border transition-all duration-300"
          :class="showDebug
            ? 'bg-flame/30 text-flame border-flame/50 shadow-[0_0_12px_rgba(255,106,0,0.3)]'
            : 'bg-black/50 text-gray-500 border-white/10 hover:border-flame/30 hover:text-flame'"
          @click="toggleDebug"
          title="按 D 键切换调试面板"
        >
          {{ showDebug ? '🐛 ON' : '🐛 DEBUG' }}
        </button>
      </div>
      <ControlBar
        :is-idle="training.isIdle.value"
        :is-paused="training.state.value === 'paused'"
        :current="currentExercise"
        :exercises="exercises"
        :target-reps="targetReps"
        @start="startTraining"
        @stop="handleStop"
        @pause="togglePause"
        @exercise="switchExercise"
        @target="handleTarget"
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

  <!-- Training summary overlay -->
  <TrainingSummary
    :visible="showSummary"
    :data="summaryData"
    @close="dismissSummary"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { ScoreData, PoseContext, SummaryData, ErrorSummary } from './types'
import { config } from './config'
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
import PoseViewer from './components/PoseViewer.vue'
import DebugOverlay from './components/DebugOverlay.vue'
import TrainingSummary from './components/TrainingSummary.vue'

const camera = useCamera()
const ws = useWebSocket()
const training = useTrainingState()

// Entry screen — shown on load, dismissed on click-to-enter
const showEntry = ref(true)

// Debug mode — toggle with 'D' key or button
const showDebug = ref(false)

function toggleDebug() {
  showDebug.value = !showDebug.value
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'd' || e.key === 'D') {
    const tag = (e.target as HTMLElement)?.tagName
    if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
      toggleDebug()
    }
  }
}

onMounted(() => {
  fetchExercises()
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  stopFrameLoop()
  camera.stop()
  ws.disconnect()
  window.removeEventListener('keydown', onKeyDown)
})

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

// Target rep mode
const targetReps = ref(0)        // 0 = free mode
const targetReached = ref(false)
const showSummary = ref(false)

// Accumulated errors during session: name -> { count, severity, suggestion }
const sessionErrors = ref<Map<string, ErrorSummary>>(new Map())

// Per-rep dedup: only count each error name once per rep
const lastRepCount = ref(0)
const countedInThisRep = ref<Set<string>>(new Set())

// Snapshot captured BEFORE WebSocket disconnect (avoids reading null values)
const summarySnapshot = ref<SummaryData | null>(null)

const currentScore = computed<ScoreData>(() =>
  ws.lastResult.value?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 }
)

const totalErrors = computed(() => {
  return ws.lastResult.value?.errors?.length || 0
})

// Build pose context for AI coach
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

// Summary data — uses pre-disconnect snapshot to avoid null values
const summaryData = computed<SummaryData>(() => {
  if (summarySnapshot.value) return summarySnapshot.value
  return {
    exercise: currentExercise.value,
    totalReps: 0,
    targetReps: 0,
    bestScore: 0,
    avgScore: 0,
    duration: '0:00',
    errors: [],
    finalScore: { total: 0, angle: 0, temporal: 0, symmetry: 0 },
  }
})

// Watch score → update best & recent
watch(() => ws.lastResult.value?.score?.total, (newTotal) => {
  if (newTotal !== undefined && newTotal > 0) {
    if (newTotal > bestScore.value) bestScore.value = newTotal
    recentScores.value.push(newTotal)
    if (recentScores.value.length > 30) recentScores.value.shift()
  }
})

// Watch errors → accumulate once per rep, deduplicate by error name
// Each error type counts at most 1 per rep, regardless of how many frames it appears
watch(() => ws.lastResult.value?.errors, (errors) => {
  if (!errors || errors.length === 0) return
  const currentCount = ws.lastResult.value?.count || 0

  // Only count errors when entering a new rep
  if (currentCount > lastRepCount.value) {
    lastRepCount.value = currentCount
    countedInThisRep.value = new Set()

    for (const e of errors) {
      // Dedup: at most once per error name per rep
      if (countedInThisRep.value.has(e.name)) continue
      countedInThisRep.value.add(e.name)

      const existing = sessionErrors.value.get(e.name)
      if (existing) {
        existing.count++
      } else {
        sessionErrors.value.set(e.name, {
          name: e.name,
          count: 1,
          severity: e.severity,
          suggestion: e.suggestion,
        })
      }
    }
  }
})

// Watch rep count → auto-stop when target reached
watch(() => ws.lastResult.value?.count, (count) => {
  if (targetReps.value > 0 && count !== undefined && count >= targetReps.value && !targetReached.value) {
    targetReached.value = true
    captureSummarySnapshot()
    stopTraining(true)
    showSummary.value = true
  }
})

function handleTarget(value: number) {
  targetReps.value = value
  targetReached.value = false
}

function dismissSummary() {
  showSummary.value = false
  targetReached.value = false
}

// Fetch authoritative exercise list from backend
async function fetchExercises() {
  try {
    const res = await fetch(config.endpoints.exercises)
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

function resetSessionStats() {
  bestScore.value = 0
  recentScores.value = []
  sessionErrors.value = new Map()
  lastRepCount.value = 0
  countedInThisRep.value = new Set()
  summarySnapshot.value = null
  targetReached.value = false
}

// ---- Session lifecycle ----
async function beginSession() {
  try {
    const res = await fetch(config.endpoints.sessionStart, {
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
    await fetch(config.endpoints.sessionStop, {
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
          error_counts: {},
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

// Capture summary snapshot BEFORE WebSocket disconnects
function captureSummarySnapshot() {
  const avg = recentScores.value.length > 0
    ? recentScores.value.reduce((a, b) => a + b, 0) / recentScores.value.length
    : 0
  const r = ws.lastResult.value
  summarySnapshot.value = {
    exercise: currentExercise.value,
    totalReps: r?.count || 0,
    targetReps: targetReps.value,
    bestScore: bestScore.value,
    avgScore: avg,
    duration: training.formattedTime.value,
    errors: [...sessionErrors.value.values()],
    finalScore: r?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 },
  }
}

// handleStop: called by stop button
function handleStop() {
  const wasTargetReached = targetReps.value > 0 && (ws.lastResult.value?.count || 0) >= targetReps.value
  if (wasTargetReached) {
    captureSummarySnapshot()
  }
  stopTraining(false)
  if (wasTargetReached) {
    showSummary.value = true
  }
}

async function stopTraining(silent: boolean) {
  stopFrameLoop()
  if (!silent) {
    await endSession()
  }
  training.stop()
  camera.stop()
  ws.disconnect()
  if (!silent) {
    resetSessionStats()
  }
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
</script>
