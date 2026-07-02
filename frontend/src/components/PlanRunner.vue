<template>
  <div
    class="absolute inset-0 z-40 flex flex-col items-center justify-center bg-black/70 backdrop-blur-sm transition-opacity duration-500"
    :class="{ 'opacity-0 pointer-events-none': !visible }"
  >
    <!-- Phase badge -->
    <div v-if="phaseLabel" class="text-[10px] uppercase tracking-[4px] mb-3 px-3 py-1 rounded-full"
         :class="phaseClass">
      {{ phaseLabel }}
    </div>

    <!-- Current exercise -->
    <div class="text-5xl font-extrabold gradient-text text-center mb-1">
      {{ current.exercise }}
    </div>

    <!-- Target display -->
    <div class="text-lg font-bold mb-6" :class="isRest ? 'text-amber-400' : 'text-white'">
      <template v-if="isRest">
        休息 {{ restCountdown }}s
      </template>
      <template v-else-if="current.duration_seconds">
        保持 {{ current.duration_seconds }}s
      </template>
      <template v-else>
        <span class="text-3xl">{{ repsDone }}</span>
        <span class="text-gray-500"> / {{ repsTarget }} reps</span>
      </template>
    </div>

    <!-- Notes -->
    <div v-if="current.notes && !isRest" class="text-xs text-gray-400 mb-6 max-w-xs text-center">
      {{ current.notes }}
    </div>

    <!-- Progress bar -->
    <div class="w-64 h-1 rounded-full bg-white/[0.08] mb-6 overflow-hidden">
      <div class="h-full rounded-full bg-flame transition-all duration-500"
           :style="{ width: (totalSteps > 0 ? (stepIndex / totalSteps) * 100 : 0) + '%' }" />
    </div>

    <!-- Step dots -->
    <div class="flex gap-1.5 mb-6">
      <div v-for="(s, i) in steps" :key="i"
           class="w-1.5 h-1.5 rounded-full transition-all duration-300"
           :class="i < stepIndex ? 'bg-flame' : i === stepIndex ? 'bg-white scale-150' : 'bg-white/[0.15]'" />
    </div>

    <div class="text-[9px] text-gray-600 mb-6">步骤 {{ stepIndex + 1 }} / {{ totalSteps }}</div>

    <!-- Controls -->
    <div class="flex gap-3">
      <button v-if="isRest && restCountdown > 3"
              @click="skipRest"
              class="px-4 py-2 rounded-lg text-[11px] bg-white/[0.06] border border-white/10 text-gray-400">
        跳过休息
      </button>
      <button @click="$emit('skip')"
              class="px-4 py-2 rounded-lg text-[11px] bg-white/[0.06] border border-white/10 text-gray-400">
        跳过
      </button>
      <button @click="$emit('quit')"
              class="px-4 py-2 rounded-lg text-[11px] bg-red-500/[0.12] border border-red-500/[0.25] text-red-400">
        结束训练
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PlanStep } from '../types'

const props = defineProps<{
  visible: boolean
  steps: PlanStep[]
  stepIndex: number
  repsDone: number
  isRest: boolean
  restCountdown: number
  phaseLabel: string
  phaseClass: string
}>()

defineEmits<{ skip: []; quit: []; skipRest: [] }>()

const totalSteps = computed(() => props.steps.length)

const current = computed<PlanStep>(() => {
  return props.steps[props.stepIndex] || { exercise: '完成', reps: 0, sets: 1, rest_seconds: 0 }
})

const repsTarget = computed(() => {
  const s = current.value
  return s.duration_seconds ? s.duration_seconds : (s.reps * s.sets)
})
</script>
