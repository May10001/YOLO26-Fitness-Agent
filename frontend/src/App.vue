<template>
  <EntryScreen v-if="showEntry" @enter="showEntry = false" />

  <!-- Backend health indicator (Nike monochrome) -->
  <div
    class="fixed top-3 right-3 z-40 flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-[9px] border transition-all duration-500"
    :class="backendOnline
      ? 'bg-[#111] border-white/10 text-white'
      : 'bg-[#111] border-danger/40 text-danger'"
    :title="backendOnline ? '后端已连接' : '后端未响应 — 检查 uvicorn 是否启动'"
  >
    <span class="w-1.5 h-1.5 rounded-full" :class="backendOnline ? 'bg-success' : 'bg-danger'" />
    {{ backendOnline ? 'API 在线' : 'API 离线' }}
  </div>

  <!-- Brand logo (top-left) -->
  <img src="/assets/logo.png" alt="ForMAI" class="fixed top-3 left-3 z-40 h-7 w-auto opacity-80 hover:opacity-100 transition-opacity" />

  <div class="relative z-10 h-screen w-screen p-3 flex gap-3 bg-[#05080C]">
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
          :target-reps="effectiveTargetReps"
        />
        <PlanRunner
          :visible="planMode"
          :steps="planSteps"
          :step-index="planStepIndex"
          :reps-done="ws.lastResult.value?.count || 0"
          :is-rest="planIsRest"
          :rest-countdown="restCountdown"
          :phase-label="planPhaseLabel"
          :phase-class="planPhaseClass"
          @skip="advancePlanStep"
          @quit="quitPlanMode"
          @skip-rest="skipRest"
        />
        <!-- Debug toggle button -->
        <button
          class="absolute top-6 right-8 z-30 px-2.5 py-1 rounded-full text-[9px] font-medium border transition-all duration-300"
          :class="showDebug
            ? 'bg-obsidian text-paper border-obsidian'
            : 'bg-black/40 text-paper/70 border-white/20 hover:border-white/50 hover:text-paper'"
          @click="toggleDebug"
          title="按 D 键切换调试面板 / 骨架"
        >
          {{ showDebug ? '骨架 ON' : '骨架 / DEBUG' }}
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

      <!-- Action buttons -->
      <div class="flex gap-1.5">
        <button @click="modalCoach = true"
                class="flex-1 text-[10px] py-1.5 rounded-md font-medium border transition-colors bg-accent/10 border-accent/30 text-accent hover:bg-accent/20">
          AI教练
        </button>
        <button @click="modalQA = true"
                class="flex-1 text-[10px] py-1.5 rounded-md font-medium border transition-colors bg-white/[0.02] border-white/[0.08] text-steel hover:text-white hover:border-white/20">
          问答
        </button>
        <button @click="modalHistory = true"
                class="flex-1 text-[10px] py-1.5 rounded-md font-medium border transition-colors bg-white/[0.02] border-white/[0.08] text-steel hover:text-white hover:border-white/20">
          历史
        </button>
        <button @click="modalPlan = true"
                class="flex-1 text-[10px] py-1.5 rounded-md font-medium border transition-colors bg-white/[0.02] border-white/[0.08] text-steel hover:text-white hover:border-white/20">
          计划
        </button>
      </div>

      <!-- Utility panel (bottom-right) -->
      <div class="mt-auto flex items-center gap-2 px-1">
        <!-- Sound toggle -->
        <button @click="soundOn = !soundOn"
                class="flex items-center gap-1 px-2 py-1 rounded-md text-[9px] border transition-colors"
                :class="soundOn
                  ? 'bg-accent/10 border-accent/30 text-accent'
                  : 'bg-white/[0.02] border-white/[0.06] text-faint'"
                :title="soundOn ? '音效已开启' : '音效已关闭'">
          {{ soundOn ? '🔊' : '🔇' }}
        </button>
        <!-- FPS display -->
        <span class="text-[9px] text-faint ml-auto" title="实时帧率">
          {{ fps }} FPS
        </span>
        <!-- Session time -->
        <span class="text-[9px] text-faint" title="训练时长">
          {{ training.formattedTime.value }}
        </span>
      </div>
    </div>
  </div>

  <!-- ============================================================
       Modal overlays
       ============================================================ -->

  <!-- AI Coach modal -->
  <Transition name="modal">
    <div v-if="modalCoach" class="modal-backdrop" @click.self="modalCoach = false">
      <div class="modal-panel modal-wide">
        <div class="modal-header">
          <span class="text-xs font-semibold text-accent uppercase tracking-wider">AI 教练</span>
          <button @click="modalCoach = false" class="text-steel hover:text-white text-lg leading-none">&times;</button>
        </div>
        <AiCoach
          :pose-context="poseContext"
          :coach-message="ws.lastCoachMessage.value"
          :cue-tracking="cueTracking"
          :initial-messages="coachHistory"
          @update-history="saveCoachHistory"
        />
      </div>
    </div>
  </Transition>

  <!-- Fitness QA modal -->
  <Transition name="modal">
    <div v-if="modalQA" class="modal-backdrop" @click.self="modalQA = false">
      <div class="modal-panel modal-wide">
        <div class="modal-header">
          <span class="text-xs font-semibold text-accent uppercase tracking-wider">知识问答</span>
          <button @click="modalQA = false" class="text-steel hover:text-white text-lg leading-none">&times;</button>
        </div>
        <FitnessQA :initial-messages="qaHistory" @update-history="saveQAHistory" />
      </div>
    </div>
  </Transition>

  <!-- History modal -->
  <Transition name="modal">
    <div v-if="modalHistory" class="modal-backdrop" @click.self="modalHistory = false">
      <div class="modal-panel">
        <div class="modal-header">
          <span class="text-xs font-semibold text-accent uppercase tracking-wider">训练历史</span>
          <button @click="modalHistory = false" class="text-steel hover:text-white text-lg leading-none">&times;</button>
        </div>
        <HistoryPanel />
      </div>
    </div>
  </Transition>

  <!-- Plan modal -->
  <Transition name="modal">
    <div v-if="modalPlan" class="modal-backdrop" @click.self="modalPlan = false">
      <div class="modal-panel modal-wide max-h-[90vh] overflow-y-auto">
        <div class="modal-header">
          <span class="text-xs font-semibold text-accent uppercase tracking-wider">计划 & 画像</span>
          <button @click="modalPlan = false" class="text-steel hover:text-white text-lg leading-none">&times;</button>
        </div>
        <ProfilePage ref="profilePageRef" />
        <div class="my-3 border-t border-white/6"></div>
        <CustomPlanBuilder @start="onPlanStart; modalPlan = false" />
        <div class="my-3 border-t border-white/6"></div>
        <AIPlanGenerator
          :profile="profileData"
          @start="onPlanStart; modalPlan = false"
        />
      </div>
    </div>
  </Transition>

  <!-- Training summary overlay -->
  <TrainingSummary
    :visible="showSummary"
    :data="summaryData"
    @close="dismissSummary"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { ScoreData, PoseContext, SummaryData, ErrorSummary, PlanStep, CueTrackingData, KeyFrame } from './types'
import { config } from './config'
import { useCamera } from './composables/useCamera'
import { useWebSocket } from './composables/useWebSocket'
import { useTrainingState } from './composables/useTrainingState'
import EntryScreen from './components/EntryScreen.vue'
import VideoStage from './components/VideoStage.vue'
import ControlBar from './components/ControlBar.vue'
import ScorePanel from './components/ScorePanel.vue'
import CorrectionPanel from './components/CorrectionPanel.vue'
import AiCoach from './components/AiCoach.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import JointHeatmap from './components/JointHeatmap.vue'
import TrainingSummary from './components/TrainingSummary.vue'
import ProfilePage from './components/ProfilePage.vue'
import AIPlanGenerator from './components/AIPlanGenerator.vue'
import PlanRunner from './components/PlanRunner.vue'
import FitnessQA from './components/FitnessQA.vue'
import CustomPlanBuilder from './components/CustomPlanBuilder.vue'
import { useSound } from './composables/useSound'

const camera = useCamera()
const ws = useWebSocket()
const training = useTrainingState()
const sfx = useSound()
const soundOn = ref(true)  // sound toggle

const showEntry = ref(true)
const showDebug = ref(false)

function toggleDebug() { showDebug.value = !showDebug.value }
function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'd' || e.key === 'D') {
    const tag = (e.target as HTMLElement)?.tagName
    if (tag !== 'INPUT' && tag !== 'TEXTAREA') toggleDebug()
  }
}

// ---- Global button click sound ----
function onGlobalClick(e: MouseEvent) {
  const el = e.target as HTMLElement
  if (el.closest('button') && soundOn.value) {
    sfx.play('click')
  }
}

// ---- Backend health monitoring ----
const backendOnline = ref(false)
let healthTimer: number | null = null

async function checkHealth() {
  try {
    const res = await fetch(config.endpoints.health, { signal: AbortSignal.timeout(3000) })
    backendOnline.value = res.ok
  } catch {
    backendOnline.value = false
  }
}

onMounted(() => {
  fetchExercises()
  window.addEventListener('keydown', onKeyDown)
  document.addEventListener('click', onGlobalClick)
  sfx.ensurePreload()
  checkHealth()
  healthTimer = window.setInterval(checkHealth, 15000)
})
onUnmounted(() => {
  stopFrameLoop(); camera.stop(); ws.disconnect()
  window.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('click', onGlobalClick)
  if (healthTimer) clearInterval(healthTimer)
})

// Modal visibility
const modalCoach = ref(false)
const modalQA = ref(false)
const modalHistory = ref(false)
const modalPlan = ref(false)

// Chat history persistence (localStorage)
const COACH_HISTORY_KEY = 'formai_coach_history'
const QA_HISTORY_KEY = 'formai_qa_history'

function loadHistory(key: string): any[] {
  try { return JSON.parse(localStorage.getItem(key) || '[]') } catch { return [] }
}
function saveHistory(key: string, messages: any[]) {
  try { localStorage.setItem(key, JSON.stringify(messages.slice(-50))) } catch {}
}

const coachHistory = ref<any[]>(loadHistory(COACH_HISTORY_KEY))
const qaHistory = ref<any[]>(loadHistory(QA_HISTORY_KEY))

function saveCoachHistory(msgs: any[]) { coachHistory.value = msgs; saveHistory(COACH_HISTORY_KEY, msgs) }
function saveQAHistory(msgs: any[]) { qaHistory.value = msgs; saveHistory(QA_HISTORY_KEY, msgs) }

const exercises = ref<string[]>(['深蹲', '俯卧撑', '平板支撑', '卷腹', '开合跳'])
const currentExercise = ref('深蹲')
const fps = ref(0)
let frameInterval: number | null = null
let frameCount = 0
let fpsTimer: number | null = null

const sessionId = ref<string | null>(null)
const sessionStartTime = ref(0)
const bestScore = ref(0)
const recentScores = ref<number[]>([])

const targetReps = ref(0)
const targetReached = ref(false)
const showSummary = ref(false)
const sessionErrors = ref<Map<string, ErrorSummary>>(new Map())
const lastRepCount = ref(0)
const countedInThisRep = ref<Set<string>>(new Set())
const summarySnapshot = ref<SummaryData | null>(null)
const sessionFrames = ref<KeyFrame[]>([])  // captured key frames

// ---- Plan mode ----
const planMode = ref(false)
const planSteps = ref<PlanStep[]>([])
const planStepIndex = ref(0)
const planIsRest = ref(false)
const restCountdown = ref(0)
const planPhaseLabel = ref('')
const planPhaseClass = ref('')
let restTimer: number | null = null

// Profile ref for reading data
const profilePageRef = ref<InstanceType<typeof ProfilePage> | null>(null)
const profileData = computed(() => profilePageRef.value?.form || {
  name: '用户', age: 25, weight_kg: 70, height_cm: 170,
  goal: 'general', fitness_level: 'beginner', equipment: 'mat',
  training_days_per_week: 3, injury_history: '', liked_exercises: [], disliked_exercises: [],
})

// Effective target: plan mode uses step reps, free mode uses targetReps
const effectiveTargetReps = computed(() => {
  if (planMode.value && planSteps.value[planStepIndex.value]) {
    const s = planSteps.value[planStepIndex.value]
    if (s.duration_seconds) return 0 // hold exercises don't count reps
    return s.reps * s.sets
  }
  return targetReps.value
})

const currentScore = computed<ScoreData>(() =>
  ws.lastResult.value?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 }
)
const totalErrors = computed(() => ws.lastResult.value?.errors?.length || 0)
const cueTracking = computed<CueTrackingData | null>(() => ws.lastResult.value?.cue_tracking || null)

const poseContext = computed<PoseContext>(() => {
  const r = ws.lastResult.value
  return {
    exercise_name: currentExercise.value, score: r?.score, phase: r?.phase,
    rep_count: r?.count ?? 0, hold_time: r?.hold_time ?? 0, errors: r?.errors,
    best_score: bestScore.value, recent_scores: [...recentScores.value], chat_mode: 'reactive',
  }
})

const summaryData = computed<SummaryData>(() => {
  if (summarySnapshot.value) return summarySnapshot.value
  return { exercise: currentExercise.value, totalReps: 0, targetReps: 0, bestScore: 0, avgScore: 0, duration: '0:00', errors: [], finalScore: { total: 0, angle: 0, temporal: 0, symmetry: 0 } }
})

// ---- Watch score + capture highlight frames ----
watch(() => ws.lastResult.value?.score?.total, (newTotal) => {
  if (newTotal !== undefined && newTotal > 0) {
    if (newTotal > bestScore.value && bestScore.value > 0) {
      // Personal best: capture highlight frame
      if (sessionFrames.value.length < 12) {
        const frame = camera.captureFrame()
        if (frame) {
          sessionFrames.value.push({
            type: 'highlight',
            label: `最佳 ${newTotal.toFixed(0)} 分`,
            image: frame,
            timestamp: new Date().toLocaleTimeString(),
          })
        }
      }
    }
    if (newTotal > bestScore.value) bestScore.value = newTotal
    recentScores.value.push(newTotal)
    if (recentScores.value.length > 30) recentScores.value.shift()
  }
})

// ---- Per-rep error counting + key frame capture ----
watch(() => ws.lastResult.value?.errors, (errors) => {
  if (!errors || errors.length === 0) return
  const currentCount = ws.lastResult.value?.count || 0
  if (currentCount > lastRepCount.value) {
    lastRepCount.value = currentCount
    countedInThisRep.value = new Set()
    // Rep complete sound
    if (soundOn.value) sfx.play('succeed')
    // Capture error frame (first error per rep)
    let capturedThisRep = false
    for (const e of errors) {
      if (countedInThisRep.value.has(e.name)) continue
      countedInThisRep.value.add(e.name)
      const existing = sessionErrors.value.get(e.name)
      if (existing) { existing.count++ }
      else { sessionErrors.value.set(e.name, { name: e.name, count: 1, severity: e.severity, suggestion: e.suggestion }) }
      // Capture key frame for first occurrence of each error type
      if (!existing && sessionFrames.value.length < 12) {
        const frame = camera.captureFrame()
        if (frame) {
          sessionFrames.value.push({
            type: 'error',
            label: e.name,
            image: frame,
            timestamp: new Date().toLocaleTimeString(),
          })
        }
      }
      if (!capturedThisRep && sessionFrames.value.length < 12) {
        capturedThisRep = true
      }
    }
  }
})

// ---- Plan step progression ----
watch(() => ws.lastResult.value?.count, (count) => {
  // Plan mode: advance when reps done
  if (planMode.value && !planIsRest.value && count !== undefined && count > 0) {
    const step = planSteps.value[planStepIndex.value]
    if (step && !step.duration_seconds) {
      const target = step.reps * step.sets
      if (count >= target) {
        // Step complete → start rest or next
        if (step.rest_seconds > 0 && planStepIndex.value < planSteps.value.length - 1) {
          startRest(step.rest_seconds)
        } else {
          advancePlanStep()
        }
      }
    }
  }
  // Free mode: target reached
  if (!planMode.value && targetReps.value > 0 && count !== undefined && count >= targetReps.value && !targetReached.value) {
    targetReached.value = true
    captureSummarySnapshot()
    stopTraining(true)
    showSummary.value = true
  }
})

function onPlanStart(steps: PlanStep[]) {
  if (steps.length === 0) return
  planSteps.value = steps
  planStepIndex.value = 0
  planIsRest.value = false
  planMode.value = true
  applyPlanStep()
  // Auto-start training
  startTraining()
}

function applyPlanStep() {
  const step = planSteps.value[planStepIndex.value]
  if (!step) return
  ws.reset()
  // Determine phase label
  if (planStepIndex.value === 0) {
    planPhaseLabel.value = '热身'
    planPhaseClass.value = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
  } else if (planStepIndex.value >= planSteps.value.length - (planSteps.value[planSteps.value.length - 1]?.duration_seconds ? 1 : 0)) {
    planPhaseLabel.value = '整理'
    planPhaseClass.value = 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
  } else {
    planPhaseLabel.value = '训练'
    planPhaseClass.value = 'bg-flame/20 text-flame border border-flame/30'
  }
  // Set exercise and target
  if (currentExercise.value !== step.exercise) {
    currentExercise.value = step.exercise
    ws.setExercise(step.exercise)
  }
  lastRepCount.value = 0
}

function startRest(seconds: number) {
  planIsRest.value = true
  restCountdown.value = seconds
  restTimer = window.setInterval(() => {
    restCountdown.value--
    if (restCountdown.value <= 0) {
      if (restTimer) clearInterval(restTimer)
      planIsRest.value = false
      advancePlanStep()
    }
  }, 1000)
}

function skipRest() {
  if (restTimer) clearInterval(restTimer)
  restCountdown.value = 0
  planIsRest.value = false
  advancePlanStep()
}

function advancePlanStep() {
  if (planStepIndex.value >= planSteps.value.length - 1) {
    // Plan complete
    captureSummarySnapshot()
    quitPlanModeInternal()
    showSummary.value = true
    return
  }
  planStepIndex.value++
  ws.reset()
  lastRepCount.value = 0
  applyPlanStep()
}

function quitPlanMode() {
  quitPlanModeInternal()
  handleStop()
}

function quitPlanModeInternal() {
  planMode.value = false
  planSteps.value = []
  planStepIndex.value = 0
  planIsRest.value = false
  if (restTimer) { clearInterval(restTimer); restTimer = null }
}

// ---- Stop handler ----
function handleStop() {
  const wasTargetReached = !planMode.value && targetReps.value > 0 && (ws.lastResult.value?.count || 0) >= targetReps.value
  if (wasTargetReached) captureSummarySnapshot()
  stopTraining(false)
  if (wasTargetReached) showSummary.value = true
}

function captureSummarySnapshot() {
  const avg = recentScores.value.length > 0
    ? recentScores.value.reduce((a, b) => a + b, 0) / recentScores.value.length : 0
  const r = ws.lastResult.value
  summarySnapshot.value = {
    exercise: currentExercise.value, totalReps: r?.count || 0, targetReps: targetReps.value,
    bestScore: bestScore.value, avgScore: avg, duration: training.formattedTime.value,
    errors: [...sessionErrors.value.values()],
    finalScore: r?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 },
    frames: [...sessionFrames.value],
  }
}

function handleTarget(value: number) { targetReps.value = value; targetReached.value = false }
function dismissSummary() { showSummary.value = false; targetReached.value = false }

// Auto-save workout record when score >= 80
async function autoSaveWorkoutRecord() {
  const snap = summarySnapshot.value
  if (!snap || snap.bestScore < 80) return
  try {
    const name = profileData.value.name || '用户'
    // Load current profile
    const loadRes = await fetch(config.endpoints.profileLoad(name))
    if (!loadRes.ok) return
    const prof = await loadRes.json()
    // Build workout record
    const record = {
      date: new Date().toISOString().slice(0, 16),
      exercise: snap.exercise,
      total_reps: snap.totalReps,
      best_score: snap.bestScore,
      avg_score: Math.round(snap.avgScore),
      duration: snap.duration,
      errors: snap.errors,
    }
    // Append to history (keep last 30)
    const history = prof.workout_history || []
    history.unshift(record)
    if (history.length > 30) history.length = 30
    prof.workout_history = history
    // Update pain points
    const points = prof.pain_points || []
    for (const err of snap.errors) {
      const existing = points.find((p: any) => p.error_name === err.name)
      if (existing) { existing.count += err.count; existing.last_seen = record.date }
      else { points.push({ error_name: err.name, count: err.count, last_seen: record.date, suggestion: err.suggestion }) }
    }
    prof.pain_points = points
    // Save back
    await fetch(config.endpoints.profile, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(prof),
    })
  } catch { /* non-critical */ }
}

// Play milestone sound and auto-save on summary
watch(showSummary, (v) => {
  if (v && soundOn.value) sfx.play('milestone')
  if (v) autoSaveWorkoutRecord()
})

async function fetchExercises() {
  try {
    const res = await fetch(config.endpoints.exercises)
    if (!res.ok) return
    const data = await res.json()
    if (data.exercises && Array.isArray(data.exercises) && data.exercises.length > 0) {
      exercises.value = data.exercises
      if (!data.exercises.includes(currentExercise.value)) currentExercise.value = data.exercises[0]
    }
  } catch { /* keep fallback */ }
}

function resetSessionStats() {
  bestScore.value = 0; recentScores.value = []
  sessionErrors.value = new Map(); lastRepCount.value = 0
  countedInThisRep.value = new Set(); summarySnapshot.value = null
  sessionFrames.value = []
  targetReached.value = false
}

async function beginSession() {
  try {
    const res = await fetch(config.endpoints.sessionStart, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise: currentExercise.value }),
    })
    const data = await res.json()
    sessionId.value = data.session_id || null; sessionStartTime.value = Date.now()
  } catch { /* non-critical */ }
}

async function endSession() {
  if (!sessionId.value) return
  try {
    const duration = (Date.now() - sessionStartTime.value) / 1000
    await fetch(config.endpoints.sessionStop, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value, duration_seconds: duration,
        stats: { total_reps: ws.lastResult.value?.count || 0, best_score: bestScore.value,
          avg_score: recentScores.value.length > 0 ? recentScores.value.reduce((a, b) => a + b, 0) / recentScores.value.length : 0, error_counts: {} },
      }),
    })
  } catch { /* non-critical */ }
  sessionId.value = null
}

async function startTraining() {
  await camera.start(); ws.connect(); training.start(); resetSessionStats()
  await beginSession()
  const waitOpen = setInterval(() => {
    if (ws.connected.value) { clearInterval(waitOpen); ws.setExercise(currentExercise.value); startFrameLoop() }
  }, 100)
}

async function stopTraining(silent: boolean) {
  stopFrameLoop()
  if (!silent) await endSession()
  training.stop(); camera.stop(); ws.disconnect()
  if (!silent) resetSessionStats()
}

function togglePause() {
  if (training.state.value === 'paused') { training.resume(); startFrameLoop() }
  else { training.pause(); stopFrameLoop() }
}

function switchExercise(name: string) { currentExercise.value = name; ws.setExercise(name); ws.reset(); resetSessionStats() }

function startFrameLoop() {
  frameInterval = window.setInterval(() => { const frame = camera.captureFrame(); if (frame) { ws.sendFrame(frame); frameCount++ } }, 33)
  fpsTimer = window.setInterval(() => { fps.value = frameCount; frameCount = 0 }, 1000)
}

function stopFrameLoop() { if (frameInterval) clearInterval(frameInterval); if (fpsTimer) clearInterval(fpsTimer) }
</script>
