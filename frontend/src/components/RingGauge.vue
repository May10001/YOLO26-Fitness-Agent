<template>
  <div class="text-center">
    <svg width="58" height="58" viewBox="0 0 58 58">
      <circle cx="29" cy="29" r="23" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
      <circle cx="29" cy="29" r="23" fill="none" :stroke="ringColor" stroke-width="5"
        stroke-linecap="round" :stroke-dasharray="circumference"
        :stroke-dashoffset="offset" transform="rotate(-90 29 29)"
        :filter="ringGlow" />
      <text x="29" y="33" text-anchor="middle" font-size="14" font-weight="700" :fill="ringColor" font-family="Jost, Inter, sans-serif">{{ value }}</text>
    </svg>
    <div class="text-[9px] text-steel mt-0.5">{{ label }} /{{ max }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ value: number; max: number; label: string }>()
const circumference = 2 * Math.PI * 23
const offset = computed(() => circumference * (1 - Math.min(props.value / props.max, 1)))

const ratio = computed(() => Math.min(props.value / Math.max(props.max, 1), 1))

const ringColor = computed(() => {
  if (ratio.value >= 0.75) return '#38D6B2'  // green
  if (ratio.value >= 0.5) return '#F2AA4C'   // amber
  return '#E05C7B'                           // red
})

const ringGlow = computed(() => {
  if (ratio.value >= 0.75) return 'drop-shadow(0 0 6px rgba(56,214,178,0.4))'
  if (ratio.value >= 0.5) return 'none'
  return 'drop-shadow(0 0 6px rgba(224,92,123,0.4))'
})
</script>
