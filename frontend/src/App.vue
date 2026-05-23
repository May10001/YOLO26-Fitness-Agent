<template>
  <ParticleBackground :is-training="training.isRunning.value" />
  <div class="relative z-10 h-screen w-screen p-3 flex gap-3">
    <div class="flex-[2.2] flex flex-col gap-3">
      <VideoStage
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
import { ref, computed, onUnmounted } from 'vue'
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
