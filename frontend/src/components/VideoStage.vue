<template>
  <div class="rounded-2xl overflow-visible relative bg-[#e8e8ec] border border-white/10 transition-all duration-500">
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

    <!-- HUD top bar: compact info row -->
    <div class="absolute top-3 left-4 right-4 flex items-center gap-2 z-10">
      <span v-if="isRunning" class="px-2 py-0.5 rounded-full text-[9px] font-bold text-white bg-danger shrink-0">REC</span>
      <span class="px-2 py-0.5 rounded-full text-[10px] text-white/90 bg-black/50 backdrop-blur border border-white/10 truncate">{{ exercise }}</span>
      <span v-if="result?.phase" class="px-2 py-0.5 rounded-full text-[9px] text-white/70 bg-black/40 backdrop-blur border border-white/8 shrink-0">{{ result.phase }}</span>
      <span class="ml-auto text-[10px] text-white/50 bg-black/30 backdrop-blur px-2 py-0.5 rounded-full">{{ formattedTime }} · {{ fps }}fps</span>
    </div>

    <!-- Center: guidance banner (LLM feedback — highest priority, stays center) -->
    <div v-if="guidance && isRunning"
         class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 transition-all duration-300 max-w-[92%] w-[440px]"
         :class="guidanceBannerClass">
      <div class="flex flex-col items-center gap-1.5 px-7 py-5 rounded-2xl text-center border-2 shadow-2xl"
           :class="guidanceBannerInner">
        <span class="text-[11px] uppercase tracking-widest font-bold opacity-90">{{ guidanceTypeLabel }}</span>
        <span class="text-xl font-extrabold leading-snug">{{ guidance.text }}</span>
      </div>
    </div>

    <!-- Bottom-left: compact rep ring + hold time -->
    <div v-if="isRunning && !isHoldExercise" class="absolute bottom-4 left-4 z-10">
      <div class="relative w-24 h-24">
        <svg class="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="6" />
          <circle v-if="targetReps > 0" cx="50" cy="50" r="40" fill="none" stroke="#38D6B2" stroke-width="6" stroke-linecap="round"
                  :stroke-dasharray="ringCircumference" :stroke-dashoffset="ringOffset"
                  class="rep-ring transition-all duration-500" />
          <circle v-else cx="50" cy="50" r="40" fill="none" stroke="#38D6B2" stroke-width="6" stroke-linecap="round"
                  stroke-dasharray="251" :stroke-dashoffset="ringPulseOffset"
                  class="rep-ring transition-all duration-300" />
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center">
          <div class="text-3xl font-display font-bold text-white leading-none tabular-nums">{{ result?.count || 0 }}</div>
          <div v-if="targetReps > 0" class="text-[9px] text-gray-400 leading-none">/{{ targetReps }}</div>
        </div>
      </div>
    </div>
    <div v-if="isRunning && isHoldExercise" class="absolute bottom-6 left-6 text-center z-10">
      <div class="text-4xl font-display font-semibold text-white leading-none">{{ formattedHoldTime }}</div>
      <div class="text-[9px] text-white/50 uppercase tracking-wider mt-0.5">HOLD</div>
    </div>

    <!-- Bottom-right: total score -->
    <div class="absolute bottom-4 right-4 bg-black/60 backdrop-blur border border-white/15 rounded-xl px-4 py-2.5 text-center z-10">
      <div class="text-4xl font-display font-extrabold gradient-text leading-none">{{ score.total.toFixed(0) }}</div>
      <div class="text-[8px] text-white/45 mt-0.5 uppercase tracking-[2px]">Score</div>
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
const RING_RADIUS = 40
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
