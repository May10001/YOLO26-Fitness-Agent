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
    <div class="text-5xl font-display font-semibold text-paper text-center mb-1">
      {{ current.exercise }}
    </div>

    <!-- Target display -->
    <div class="text-lg font-medium mb-6" :class="isRest ? 'text-amber-400' : 'text-paper'">
      <template v-if="isRest">
        休息 {{ restCountdown }}s
      </template>
      <template v-else-if="current.duration_seconds">
        保持 {{ current.duration_seconds }}s
      </template>
      <template v-else>
        <span class="text-3xl font-display">{{ repsDone }}</span>
        <span class="text-paper/50"> / {{ repsTarget }} reps</span>
      </template>
    </div>

    <!-- Notes -->
    <div v-if="current.notes && !isRest" class="text-xs text-paper/70 mb-6 max-w-xs text-center">
      {{ current.notes }}
    </div>

    <!-- Progress bar -->
    <div class="w-64 h-1 rounded-full bg-white/[0.15] mb-6 overflow-hidden">
      <div class="h-full rounded-full bg-paper transition-all duration-500"
           :style="{ width: (totalSteps > 0 ? (stepIndex / totalSteps) * 100 : 0) + '%' }" />
    </div>

    <!-- Step dots -->
    <div class="flex gap-1.5 mb-6">
      <div v-for="(s, i) in steps" :key="i"
           class="w-1.5 h-1.5 rounded-full transition-all duration-300"
           :class="i < stepIndex ? 'bg-flame' : i === stepIndex ? 'bg-white scale-150' : 'bg-white/[0.2]'" />
    </div>

    <div class="text-[9px] text-paper/50 mb-6">步骤 {{ stepIndex + 1 }} / {{ totalSteps }}</div>

    <!-- Controls -->
    <div class="flex gap-3">
      <button v-if="isRest && restCountdown > 3"
              @click="skipRest"
              class="px-4 py-2 rounded-full text-[11px] border border-white/30 text-paper/80 hover:bg-white/10 transition-colors">
        跳过休息
      </button>
      <button @click="$emit('skip')"
              class="px-4 py-2 rounded-full text-[11px] border border-white/30 text-paper/80 hover:bg-white/10 transition-colors">
        跳过
      </button>
      <button @click="$emit('quit')"
              class="px-4 py-2 rounded-full text-[11px] border border-danger/50 text-danger hover:bg-danger/10 transition-colors">
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
