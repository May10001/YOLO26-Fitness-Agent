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

    <!-- HUD bottom-left -->
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

    <!-- Ready overlay -->
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
  result: DetectionResult | null
  exercise: string
  isRunning: boolean
  formattedTime: string
  fps: number
}>()

const score = computed<ScoreData>(() => props.result?.score || { total: 0, angle: 0, temporal: 0, symmetry: 0 })

const glowClass = computed(() => {
  const t = score.value.total
  if (t >= 80) return 'border border-flame/30 shadow-[0_0_60px_rgba(255,106,0,0.12)]'
  if (t >= 60) return 'border border-flame/15 shadow-[0_0_30px_rgba(255,106,0,0.06)]'
  return 'border border-white/10 shadow-none'
})
</script>
