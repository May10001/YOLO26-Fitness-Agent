<template>
  <div
    class="rounded-2xl overflow-hidden relative bg-[#0a0a0a] border transition-all duration-700 min-h-[200px]"
    :class="panelGlow"
  >
    <!-- Reference grid -->
    <svg class="absolute inset-0 w-full h-full opacity-[0.04] pointer-events-none">
      <defs>
        <pattern id="poseGrid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" stroke-width="0.5" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#poseGrid)" />
      <!-- Center crosshair -->
      <line x1="50%" y1="0" x2="50%" y2="100%" stroke="white" stroke-width="0.5" />
      <line x1="0" y1="50%" x2="100%" y2="50%" stroke="white" stroke-width="0.5" />
    </svg>

    <!-- Skeleton canvas -->
    <div v-if="keypoints" class="absolute inset-4">
      <SkeletonOverlay
        :keypoints="keypoints"
        :errors="errors"
        :video-width="640"
        :video-height="480"
        :contain="true"
      />
    </div>

    <!-- Placeholder: waiting for pose data -->
    <div v-else class="absolute inset-0 flex items-center justify-center">
      <div class="text-center">
        <div class="text-[11px] text-gray-500 animate-breathe">等待动作捕捉</div>
        <div class="text-[9px] text-gray-600 mt-1.5">请面对摄像头开始训练</div>
      </div>
    </div>

    <!-- Top label -->
    <div class="absolute top-3 left-4 text-[10px] text-gray-500 uppercase tracking-wider z-10">
      姿态视图
    </div>

    <!-- Bottom-right: score mini -->
    <div v-if="scoreTotal > 0" class="absolute bottom-3 right-4 text-[10px] text-gray-600 z-10">
      SCORE <span class="text-flame font-bold">{{ scoreTotal }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SkeletonOverlay from './SkeletonOverlay.vue'

const props = defineProps<{
  keypoints: number[][] | null
  errors: { name: string; severity: number; message: string; suggestion: string }[]
  scoreTotal: number
}>()

const panelGlow = computed(() => {
  if (!props.keypoints) return 'border-white/5'
  if (props.scoreTotal >= 80) return 'border-flame/30 shadow-[0_0_40px_rgba(255,106,0,0.08)]'
  if (props.scoreTotal >= 60) return 'border-flame/15 shadow-[0_0_20px_rgba(255,106,0,0.04)]'
  return 'border-white/10'
})
</script>
