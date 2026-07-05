<template>
  <div class="flat-card p-4">
    <div class="flex justify-between items-center mb-3">
      <span class="text-[10px] uppercase tracking-wider text-steel font-medium">Score Detail</span>
      <span class="text-[10px] text-steel">第 {{ count }} 次</span>
    </div>
    <div class="flex gap-3 justify-center mb-3">
      <RingGauge :value="score.angle" :max="40" label="角度" color="#111111" />
      <RingGauge :value="score.temporal" :max="30" label="时序" color="#111111" />
      <RingGauge :value="score.symmetry" :max="30" label="对称" color="#111111" />
    </div>
    <div class="grid grid-cols-3 gap-1.5">
      <div v-if="isHoldExercise"
           class="mist-card p-2.5 text-center">
        <div class="text-2xl font-display font-semibold text-obsidian">{{ formattedHoldTime }}</div>
        <div class="text-[9px] text-steel mt-0.5">保持时长</div>
      </div>
      <div v-else
           class="mist-card p-2.5 text-center">
        <div class="text-2xl font-display font-semibold text-obsidian">{{ count }}</div>
        <div class="text-[9px] text-steel mt-0.5">总次数</div>
      </div>
      <div class="mist-card p-2.5 text-center">
        <div class="text-2xl font-display font-semibold text-obsidian">{{ formattedTime }}</div>
        <div class="text-[9px] text-steel mt-0.5">训练时长</div>
      </div>
      <div class="mist-card p-2.5 text-center">
        <div class="text-2xl font-display font-semibold" :class="errorCount > 0 ? 'text-danger' : 'text-obsidian'">{{ errorCount }}</div>
        <div class="text-[9px] text-steel mt-0.5">错误次数</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScoreData } from '../types'
import RingGauge from './RingGauge.vue'

const props = defineProps<{
  score: ScoreData
  count: number
  holdTime: number
  formattedTime: string
  errorCount: number
  exercise: string
}>()

const HOLD_EXERCISES = new Set(['平板支撑', '臀桥'])
const isHoldExercise = computed(() => HOLD_EXERCISES.has(props.exercise))

const formattedHoldTime = computed(() => {
  const h = Math.floor(props.holdTime)
  const mins = Math.floor(h / 60)
  const secs = h % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})
</script>
