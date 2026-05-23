<template>
  <div class="absolute rounded-md" :style="trackStyle" />
  <div class="absolute rounded-md transition-all duration-700" :style="valueStyle" />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  direction: 'left' | 'right' | 'bottom'
  value: number
  max: number
}>()

const ratio = computed(() => Math.min(props.value / props.max, 1))

const trackStyle = computed(() => {
  const base: Record<string, string> = { background: 'rgba(255,255,255,0.06)', borderRadius: '6px' }
  if (props.direction === 'left') return { ...base, left: '10px', top: '50px', bottom: '50px', width: '10px' }
  if (props.direction === 'right') return { ...base, right: '10px', top: '50px', bottom: '50px', width: '10px' }
  return { ...base, left: '50px', right: '50px', bottom: '10px', height: '10px' }
})

const gradients: Record<string, string> = {
  left: 'linear-gradient(180deg, #ff6a00, #ee0979)',
  right: 'linear-gradient(180deg, #ee0979, #ff6a00)',
  bottom: 'linear-gradient(90deg, #ff6a00, #ee0979)',
}

const valueStyle = computed(() => {
  const glow = '0 0 14px rgba(255,106,0,0.5), 0 0 28px rgba(238,9,121,0.2)'
  const base = { background: gradients[props.direction], boxShadow: glow, borderRadius: '6px' }
  if (props.direction === 'left') return { ...base, left: '10px', top: '50px', width: '10px', height: `calc((100% - 100px) * ${ratio.value})` }
  if (props.direction === 'right') return { ...base, right: '10px', top: '50px', width: '10px', height: `calc((100% - 100px) * ${ratio.value})` }
  return { ...base, left: '50px', bottom: '10px', height: '10px', width: `calc((100% - 100px) * ${ratio.value})` }
})
</script>
