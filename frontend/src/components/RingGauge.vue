<template>
  <div class="text-center">
    <svg width="58" height="58" viewBox="0 0 58 58">
      <circle cx="29" cy="29" r="23" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
      <circle cx="29" cy="29" r="23" fill="none" :stroke="color" stroke-width="5"
        stroke-linecap="round" :stroke-dasharray="circumference"
        :stroke-dashoffset="offset" transform="rotate(-90 29 29)"
        :style="{ filter: `drop-shadow(0 0 4px ${color}80)` }" />
      <text x="29" y="33" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">{{ value }}</text>
    </svg>
    <div class="text-[9px] text-gray-500 mt-0.5">{{ label }} /{{ max }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ value: number; max: number; label: string; color: string }>()
const circumference = 2 * Math.PI * 23
const offset = computed(() => circumference * (1 - Math.min(props.value / props.max, 1)))
</script>
