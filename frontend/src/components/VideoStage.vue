<template>
  <div class="rounded-2xl overflow-hidden relative bg-[#e8e8ec] border border-white/10 transition-all duration-500">
    <video ref="videoEl" class="absolute inset-0 w-full h-full object-cover" muted playsinline />

    <!-- Skeleton overlay: hidden by default; errors-only when errors present; full when debug on -->
    <SkeletonOverlay
      v-if="result?.keypoints && skeletonMode !== 'hidden'"
      :keypoints="result.keypoints"
      :errors="result?.errors || []"
      :video-width="640"
      :video-height="480"
      fit="cover"
      :mode="skeletonMode"
    />

    <DebugOverlay
      v-if="showDebug && result?.debug"
      :debug="result.debug"
      :score="score"
      :phase="result?.phase || ''"
      :diagnostic-snapshot="result?.diagnostic_snapshot || null"
    />

    <!-- HUD top bar -->
    <div class="absolute top-3.5 left-6 flex gap-2 items-center z-10">
      <span v-if="isRunning" class="px-2.5 py-1 rounded-full text-[10px] font-semibold text-paper bg-danger">REC</span>
      <span class="px-2.5 py-1 rounded-full text-[10px] text-paper/90 bg-black/50 backdrop-blur border border-white/15">{{ exercise }}</span>
      <span v-if="result?.phase" class="px-2.5 py-1 rounded-full text-[10px] text-paper/80 bg-black/50 backdrop-blur border border-white/15">{{ result.phase }}</span>
    </div>

    <!-- Center: guidance banner -->
    <div v-if="guidance && isRunning"
         class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 transition-all duration-300 max-w-[85%]"
         :class="guidanceBannerClass">
      <div class="flex flex-col items-center gap-1 px-6 py-4 rounded-none text-center border"
           :class="guidanceBannerInner">
        <span class="text-[10px] uppercase tracking-widest opacity-80">{{ guidanceTypeLabel }}</span>
        <span class="text-lg font-semibold leading-tight">{{ guidance.text }}</span>
      </div>
    </div>

    <!-- Bottom: rep ring counter (green arc fill) -->
    <div v-if="isRunning && !isHoldExercise" class="absolute bottom-16 left-1/2 -translate-x-1/2 z-10">
      <div class="relative w-36 h-36">
        <!-- Ring SVG -->
        <svg class="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100">
          <!-- Track -->
          <circle cx="50" cy="50" r="42" fill="none"
                  stroke="rgba(255,255,255,0.06)" stroke-width="5" />
          <!-- Green fill arc -->
          <circle v-if="targetReps > 0" cx="50" cy="50" r="42" fill="none"
                  stroke="#38D6B2" stroke-width="5" stroke-linecap="round"
                  :stroke-dasharray="ringCircumference"
                  :stroke-dashoffset="ringOffset"
                  class="rep-ring transition-all duration-500" />
          <!-- Full ring when no target (pulsing green) -->
          <circle v-else cx="50" cy="50" r="42" fill="none"
                  stroke="#38D6B2" stroke-width="5" stroke-linecap="round"
                  stroke-dasharray="264" :stroke-dashoffset="ringPulseOffset"
                  class="rep-ring transition-all duration-300" />
        </svg>
        <!-- Center text -->
        <div class="absolute inset-0 flex flex-col items-center justify-center">
          <div class="text-4xl font-display font-bold text-white leading-none tabular-nums">
            {{ result?.count || 0 }}
          </div>
          <div v-if="targetReps > 0" class="text-[10px] text-gray-500 mt-0.5">
            / {{ targetReps }}
          </div>
          <div class="text-[9px] text-gray-600 uppercase tracking-[3px] mt-0.5">REPS</div>
        </div>
      </div>
    </div>

    <!-- Bottom: hold time for static exercises -->
    <div v-if="isRunning && isHoldExercise" class="absolute bottom-20 left-1/2 -translate-x-1/2 text-center z-10">
      <div class="text-6xl font-display font-semibold text-paper leading-none tabular-nums">{{ formattedHoldTime }}</div>
      <div class="text-[10px] text-paper/60 uppercase tracking-[4px] mt-1">HOLD</div>
    </div>

    <!-- Bottom-right: total score -->
    <div class="absolute bottom-6 right-6 bg-black/60 backdrop-blur border border-white/15 rounded-none px-5 py-3 text-center z-10">
      <div class="text-6xl font-display font-semibold text-paper leading-none">{{ score.total.toFixed(0) }}</div>
      <div class="text-[9px] text-paper/60 mt-1 uppercase tracking-[3px]">Total Score</div>
    </div>

    <!-- Bottom-left: meta info (time, FPS) -->
    <div class="absolute bottom-6 left-6 flex gap-2 z-10">
      <span class="px-2.5 py-1.5 rounded-none text-[11px] text-paper/80 bg-black/50 backdrop-blur border border-white/10">
        {{ formattedTime }}
      </span>
      <span class="px-2.5 py-1.5 rounded-none text-[11px] text-paper/60 bg-black/50 backdrop-blur border border-white/10">
        {{ fps }} FPS
      </span>
    </div>

    <!-- No person detected overlay -->
    <div v-if="result && !result.detected && isRunning"
         class="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm z-20">
      <div class="text-center">
        <div class="text-[13px] text-paper/90 animate-breathe mb-1">未检测到人体</div>
        <div class="text-[9px] text-paper/50">请确保全身在镜头范围内</div>
      </div>
    </div>

    <!-- Ready overlay -->
    <div v-if="!isRunning" class="absolute inset-0 flex items-center justify-center bg-black/40">
      <div class="text-center">
        <div class="text-sm text-paper uppercase tracking-[4px] font-semibold animate-breathe mb-2">READY</div>
        <div class="text-[10px] text-paper/50">点击下方开始训练</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import type { DetectionResult, ScoreData, GuidanceData } from '../types'
import SkeletonOverlay from './SkeletonOverlay.vue'
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

// Skeleton visibility: debug → full; else errors present → errors-only; else hidden
const skeletonMode = computed<'full' | 'errors-only' | 'hidden'>(() => {
  if (props.showDebug) return 'full'
  if ((props.result?.errors?.length ?? 0) > 0) return 'errors-only'
  return 'hidden'
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
  return isNegativeGuidance.value ? 'animate-[pulse_0.6s_ease-in-out]' : ''
})

const guidanceBannerInner = computed(() => {
  return isNegativeGuidance.value
    ? 'bg-danger/90 text-paper border-danger'
    : 'bg-success/90 text-obsidian border-success'
})

// ---- Rep ring counter (green arc) ----
const RING_RADIUS = 42
const ringCircumference = computed(() => 2 * Math.PI * RING_RADIUS)

const ringOffset = computed(() => {
  const total = Math.max(props.targetReps || 1, 1)
  const current = Math.min(props.result?.count || 0, total)
  const ratio = current / total
  return ringCircumference.value * (1 - ratio)
})

// Pulsing ring when no target set (breathing effect)
const ringPulseOffset = ref(ringCircumference.value * 0.3)
let pulseDir = 1
let pulseTimer: number | null = null

onMounted(() => {
  pulseTimer = window.setInterval(() => {
    const base = ringCircumference.value
    let val = ringPulseOffset.value
    val += pulseDir * base * 0.008
    if (val <= base * 0.15) pulseDir = 1
    if (val >= base * 0.5) pulseDir = -1
    ringPulseOffset.value = val
  }, 50)
})

onUnmounted(() => {
  if (pulseTimer) clearInterval(pulseTimer)
})
</script>
