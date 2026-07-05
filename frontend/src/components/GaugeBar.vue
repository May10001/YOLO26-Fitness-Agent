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
  const base: Record<string, string> = { background: '#e5e5e5', borderRadius: '6px' }
  if (props.direction === 'left') return { ...base, left: '10px', top: '50px', bottom: '50px', width: '10px' }
  if (props.direction === 'right') return { ...base, right: '10px', top: '50px', bottom: '50px', width: '10px' }
  return { ...base, left: '50px', right: '50px', bottom: '10px', height: '10px' }
})

const gradients: Record<string, string> = {
  left: '#111111',
  right: '#111111',
  bottom: '#111111',
}

const valueStyle = computed(() => {
  const base = { background: gradients[props.direction], borderRadius: '6px' }
  if (props.direction === 'left') return { ...base, left: '10px', top: '50px', width: '10px', height: `calc((100% - 100px) * ${ratio.value})` }
  if (props.direction === 'right') return { ...base, right: '10px', top: '50px', width: '10px', height: `calc((100% - 100px) * ${ratio.value})` }
  return { ...base, left: '50px', bottom: '10px', height: '10px', width: `calc((100% - 100px) * ${ratio.value})` }
})
</script>
