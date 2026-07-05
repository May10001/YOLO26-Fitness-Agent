<template>
  <div class="flat-card p-4 space-y-3">
    <div class="text-[10px] uppercase tracking-wider text-steel font-medium">Custom Plan</div>

    <!-- Exercise picker -->
    <div>
      <div class="text-[9px] text-steel mb-1.5">选择动作</div>
      <div class="flex flex-wrap gap-1.5 mb-2">
        <button v-for="ex in exerciseList" :key="ex"
                class="px-2 py-1 text-[10px] border transition-colors"
                :class="selectedEx === ex
                  ? 'bg-flame/20 text-flame border-flame/40'
                  : 'border-concrete text-steel hover:text-obsidian hover:border-steel'"
                @click="selectedEx = ex">
          {{ ex }}
        </button>
      </div>
      <!-- Quick add -->
      <div v-if="selectedEx" class="flex gap-2 items-end">
        <div>
          <label class="text-[8px] text-faint block">组数</label>
          <input v-model.number="addSets" type="number" min="1" max="10"
                 class="w-14 bg-mist border border-concrete px-2 py-1 text-[10px] text-obsidian outline-none" />
        </div>
        <div>
          <label class="text-[8px] text-faint block">次数</label>
          <input v-model.number="addReps" type="number" min="1" max="50"
                 class="w-14 bg-mist border border-concrete px-2 py-1 text-[10px] text-obsidian outline-none" />
        </div>
        <div>
          <label class="text-[8px] text-faint block">休息(s)</label>
          <input v-model.number="addRest" type="number" min="0" max="300"
                 class="w-14 bg-mist border border-concrete px-2 py-1 text-[10px] text-obsidian outline-none" />
        </div>
        <button @click="addExercise"
                class="pill-btn px-4 py-1.5 text-[10px]">
          添加
        </button>
      </div>
    </div>

    <!-- Plan list -->
    <div v-if="plan.length > 0">
      <div class="text-[9px] text-steel mb-1.5">计划列表 ({{ plan.length }} 项)</div>
      <div class="space-y-1 max-h-[240px] overflow-y-auto">
        <div v-for="(item, i) in plan" :key="i"
             class="flex items-center gap-2 mist-card px-3 py-2">
          <span class="text-[9px] text-faint w-4">{{ i + 1 }}</span>
          <span class="text-[11px] text-obsidian font-medium flex-1">{{ item.exercise }}</span>
          <span class="text-[10px] text-steel">{{ item.sets }}×{{ item.reps }}</span>
          <span class="text-[9px] text-faint">{{ item.rest_seconds }}s</span>
          <button @click="removeExercise(i)" class="text-[9px] text-danger hover:underline">删除</button>
        </div>
      </div>
    </div>

    <!-- Start button -->
    <button v-if="plan.length > 0" @click="startPlan"
            class="pill-btn w-full py-2.5 text-xs">
      开始训练 ({{ plan.length }} 项)
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { PlanStep } from '../types'

const EXERCISE_LIST = ['深蹲', '俯卧撑', '平板支撑', '卷腹', '开合跳', '引体向上', '臀桥', '高抬腿', '肩推', '侧平举']
const exerciseList = ref(EXERCISE_LIST)

const emit = defineEmits<{ start: [steps: PlanStep[]] }>()

const selectedEx = ref('')
const addSets = ref(3)
const addReps = ref(12)
const addRest = ref(60)
const plan = ref<PlanStep[]>([])

function addExercise() {
  if (!selectedEx.value) return
  plan.value.push({
    exercise: selectedEx.value,
    sets: addSets.value,
    reps: addReps.value,
    rest_seconds: addRest.value,
  })
  selectedEx.value = ''
}

function removeExercise(i: number) {
  plan.value.splice(i, 1)
}

function startPlan() {
  emit('start', [...plan.value])
}
</script>
