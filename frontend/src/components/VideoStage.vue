<template>
  <div class="flex-1 rounded-2xl overflow-hidden relative transition-all duration-700" :class="glowClass">
    <video ref="videoEl" class="w-full h-full object-cover" muted playsinline />
    <SkeletonOverlay
      v-if="result?.keypoints"
      :keypoints="result.keypoints"
      :errors="result.errors || []"
      :video-width="640"
      :video-height="480"
    />
    <GaugeBar direction="left" :value="score.angle" :max="40" />
    <GaugeBar direction="right" :value="score.symmetry" :max="30" />
    <GaugeBar direction="bottom" :value="score.temporal" :max="30" />

    <!-- Gauge labels -->
    <div class="absolute left-[26px] top-[38px] text-[10px] font-semibold text-flame">角度 <span class="text-gray-500 text-[9px]">{{ score.angle.toFixed(0) }}/40</span></div>
    <div class="absolute right-[26px] top-[38px] text-[10px] font-semibold text-rose text-right">对称 <span class="text-gray-500 text-[9px]">{{ score.symmetry.toFixed(0) }}/30</span></div>
    <div class="absolute left-[30px] bottom-[26px] text-[10px] font-semibold text-flame">时序 <span class="text-gray-500 text-[9px]">{{ score.temporal.toFixed(0) }}/30</span></div>

    <!-- HUD top -->
    <div class="absolute top-3.5 left-7 flex gap-2 items-center">
      <span v-if="isRunning" class="px-2.5 py-1 rounded-full text-[10px] font-bold text-white bg-gradient-to-r from-flame to-rose shadow-[0_0_12px_rgba(255,106,0,0.4)]">REC</span>
      <span class="px-2.5 py-1 rounded-full text-[10px] text-gray-300 bg-black/60 backdrop-blur border border-white/10">{{ exercise }}</span>
      <span v-if="result?.phase" class="px-2.5 py-1 rounded-full text-[10px] text-emerald-400 bg-black/60 backdrop-blur border border-emerald-500/30">{{ result.phase }}</span>
    </div>

    <!-- HUD bottom-left: rep count / hold time -->
    <div class="absolute bottom-[46px] left-7 flex gap-1.5">
      <span v-if="isHoldExercise" class="px-2.5 py-1 rounded-lg text-[10px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">保持 <b class="text-flame">{{ formattedHoldTime }}</b></span>
      <span v-else class="px-2.5 py-1 rounded-lg text-[10px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">次数 <b class="text-flame">{{ result?.count || 0 }}</b></span>
      <span class="px-2.5 py-1 rounded-lg text-[10px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">时长 <b class="text-flame">{{ formattedTime }}</b></span>
      <span class="px-2.5 py-1 rounded-lg text-[10px] text-gray-400 bg-black/60 backdrop-blur border border-white/5">FPS <b class="text-flame">{{ fps }}</b></span>
    </div>

    <!-- HUD bottom-right score -->
    <div class="absolute bottom-7 right-7 bg-black/75 backdrop-blur-lg border border-flame/25 rounded-xl px-4 py-2 text-center">
      <div class="text-3xl font-extrabold gradient-text leading-none">{{ score.total.toFixed(0) }}</div>
      <div class="text-[9px] text-gray-500 mt-0.5">TOTAL</div>
    </div>

    <!-- Guidance hint banner -->
    <div v-if="guidance && isRunning"
         class="absolute top-14 left-1/2 -translate-x-1/2 z-30 transition-all duration-300"
         :class="guidancePillClass">
      <div class="flex items-center gap-2 px-4 py-2 rounded-full text-[11px] font-semibold shadow-lg">
        <span class="text-[10px] opacity-70">{{ guidanceTypeLabel }}</span>
        <span>{{ guidance.text }}</span>
      </div>
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
    <div v-if="!isRunning" class="absolute top-1/2 left-1/2 animate-breathe text-[11px] text-flame uppercase tracking-[3px] px-7 py-3 border border-flame/30 rounded-full bg-black/70 backdrop-blur">
      READY — 点击开始训练
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DetectionResult, ScoreData, GuidanceData } from '../types'
import GaugeBar from './GaugeBar.vue'
import SkeletonOverlay from './SkeletonOverlay.vue'

const props = defineProps<{
  result: DetectionResult | null
  guidance: GuidanceData | null
  exercise: string
  isRunning: boolean
  formattedTime: string
  fps: number
  stream: MediaStream | null
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

// ---- Guidance banner styling ----
const guidanceTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    form_correction: '纠正',
    performance: '表现',
    motivation: '鼓励',
    safety: '安全',
  }
  return labels[props.guidance?.type ?? ''] ?? ''
})

const guidancePillClass = computed(() => {
  const prio = props.guidance?.priority ?? 0
  const type = props.guidance?.type ?? ''

  if (type === 'safety' || prio >= 4) {
    return 'bg-danger/80 text-white border border-danger shadow-[0_0_20px_rgba(255,77,77,0.5)]'
  }
  if (prio >= 3) {
    return 'bg-flame/80 text-white border border-flame shadow-[0_0_20px_rgba(255,106,0,0.5)]'
  }
  return 'bg-black/70 backdrop-blur text-flame border border-flame/30'
})
</script>
