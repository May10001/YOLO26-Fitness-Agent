<template>
  <div class="rounded-2xl overflow-hidden relative transition-all duration-700" :class="glowClass">
    <video ref="videoEl" class="absolute inset-0 w-full h-full object-cover" muted playsinline />
    <DebugOverlay
      v-if="showDebug && result?.debug"
      :debug="result.debug"
      :score="score"
      :phase="result?.phase || ''"
    />

    <!-- HUD top bar -->
    <div class="absolute top-3.5 left-7 flex gap-2 items-center">
      <span v-if="isRunning" class="px-2.5 py-1 rounded-full text-[10px] font-bold text-white bg-gradient-to-r from-flame to-rose shadow-[0_0_12px_rgba(255,106,0,0.4)]">REC</span>
      <span class="px-2.5 py-1 rounded-full text-[10px] text-gray-300 bg-black/60 backdrop-blur border border-white/10">{{ exercise }}</span>
      <span v-if="result?.phase" class="px-2.5 py-1 rounded-full text-[10px] text-emerald-400 bg-black/60 backdrop-blur border border-emerald-500/30">{{ result.phase }}</span>
    </div>

    <!-- Center: guidance banner (large, color-coded) -->
    <div v-if="guidance && isRunning"
         class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 transition-all duration-300 max-w-[85%]"
         :class="guidanceBannerClass">
      <div class="flex flex-col items-center gap-1 px-6 py-4 rounded-2xl shadow-2xl text-center"
           :class="guidanceBannerInner">
        <span class="text-[10px] uppercase tracking-widest opacity-80">{{ guidanceTypeLabel }}</span>
        <span class="text-lg font-extrabold leading-tight">{{ guidance.text }}</span>
      </div>
    </div>

    <!-- Bottom: big rep counter -->
    <div v-if="isRunning && !isHoldExercise" class="absolute bottom-20 left-1/2 -translate-x-1/2 text-center z-10">
      <div class="text-6xl font-extrabold gradient-text leading-none tabular-nums">
        {{ result?.count || 0 }}<span v-if="targetReps > 0" class="text-2xl text-gray-600"> / {{ targetReps }}</span>
      </div>
      <div class="text-[10px] text-gray-500 uppercase tracking-[4px] mt-1">REPS</div>
    </div>

    <!-- Bottom: hold time for static exercises -->
    <div v-if="isRunning && isHoldExercise" class="absolute bottom-20 left-1/2 -translate-x-1/2 text-center z-10">
      <div class="text-6xl font-extrabold gradient-text leading-none tabular-nums">{{ formattedHoldTime }}</div>
      <div class="text-[10px] text-gray-500 uppercase tracking-[4px] mt-1">HOLD</div>
    </div>

    <!-- Bottom-right: big total score -->
    <div class="absolute bottom-6 right-6 bg-black/80 backdrop-blur-lg border border-flame/30 rounded-2xl px-5 py-3 text-center z-10">
      <div class="text-6xl font-extrabold gradient-text leading-none">{{ score.total.toFixed(0) }}</div>
      <div class="text-[9px] text-gray-500 mt-1 uppercase tracking-[3px]">Total Score</div>
    </div>

    <!-- Bottom-left: meta info (time, FPS) -->
    <div class="absolute bottom-6 left-6 flex gap-2 z-10">
      <span class="px-2.5 py-1.5 rounded-lg text-[11px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">
        {{ formattedTime }}
      </span>
      <span class="px-2.5 py-1.5 rounded-lg text-[11px] text-gray-500 bg-black/60 backdrop-blur border border-white/5">
        {{ fps }} FPS
      </span>
    </div>

    <!-- No person detected overlay -->
    <div v-if="result && !result.detected && isRunning"
         class="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm z-20">
      <div class="text-center">
        <div class="text-[13px] text-gray-300 animate-breathe mb-1">未检测到人体</div>
        <div class="text-[9px] text-gray-500">请确保全身在镜头范围内</div>
      </div>
    </div>

    <!-- Ready overlay -->
    <div v-if="!isRunning" class="absolute inset-0 flex items-center justify-center bg-black/40">
      <div class="text-center">
        <div class="text-sm text-flame uppercase tracking-[4px] font-bold animate-breathe mb-2">READY</div>
        <div class="text-[10px] text-gray-500">点击下方开始训练</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DetectionResult, ScoreData, GuidanceData, DebugData } from '../types'
import DebugOverlay from './DebugOverlay.vue'

const props = defineProps<{
  result: DetectionResult | null
  guidance: GuidanceData | null
  exercise: string
  isRunning: boolean
  formattedTime: string
  fps: number
  stream: MediaStream | null
  showDebug?: boolean
  targetReps?: number
}>()

const videoEl = ref<HTMLVideoElement | null>(null)

watch(() => props.stream, (s) => {
  if (videoEl.value && s) {
    videoEl.value.srcObject = s
    videoEl.value.play()
  }
})

const score = computed<ScoreData>(() => props.result?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 })

const glowClass = computed(() => {
  const t = score.value.total
  if (t >= 80) return 'border border-flame/30 shadow-[0_0_60px_rgba(255,106,0,0.12)]'
  if (t >= 60) return 'border border-flame/15 shadow-[0_0_30px_rgba(255,106,0,0.06)]'
  return 'border border-white/10 shadow-none'
})

// ---- Hold-time display for static exercises ----
const HOLD_EXERCISES = new Set(['平板支撑', '臀桥'])
const isHoldExercise = computed(() => HOLD_EXERCISES.has(props.exercise))

const formattedHoldTime = computed(() => {
  const h = Math.floor(props.result?.hold_time ?? 0)
  const mins = Math.floor(h / 60)
  const secs = h % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

// ---- Guidance banner: red for errors, green for good ----
const guidanceTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    form_correction: '动作纠正',
    performance: '表现反馈',
    motivation: '继续加油',
    safety: '安全警告',
  }
  return labels[props.guidance?.type ?? ''] ?? ''
})

const isNegativeGuidance = computed(() => {
  const type = props.guidance?.type ?? ''
  const prio = props.guidance?.priority ?? 0
  return type === 'form_correction' || type === 'safety' || prio >= 3
})

const guidanceBannerClass = computed(() => {
  return isNegativeGuidance.value
    ? 'animate-[pulse_0.6s_ease-in-out]'
    : ''
})

const guidanceBannerInner = computed(() => {
  return isNegativeGuidance.value
    ? 'bg-red-600/85 text-white border border-red-400/40 shadow-[0_0_40px_rgba(220,38,38,0.5)]'
    : 'bg-emerald-500/85 text-white border border-emerald-300/40 shadow-[0_0_40px_rgba(16,185,129,0.5)]'
})
</script>
