<template>
  <div class="h-12 flat-card flex items-center gap-2 px-3.5">
    <button v-if="isIdle" @click="$emit('start')" class="pill-btn px-5 py-2 text-[11px]">开始训练</button>
    <template v-else>
      <button @click="$emit('stop')" class="px-4 py-2 rounded-full text-[11px] font-medium border border-danger/50 text-danger hover:bg-danger/10 transition-colors">停止</button>
      <button @click="$emit('pause')" class="px-4 py-2 rounded-full text-[11px] border border-concrete text-steel hover:text-obsidian transition-colors">
        {{ isPaused ? '继续' : '暂停' }}
      </button>
    </template>

    <!-- Target rep selector -->
    <div class="flex items-center gap-1 ml-2">
      <span class="text-[9px] text-steel mr-1">目标</span>
      <button
        v-for="opt in targetOptions" :key="opt.value"
        @click="$emit('target', opt.value)"
        class="px-2.5 py-1 text-[10px] pill-tag"
        :class="{ 'pill-tag-active': opt.value === targetReps }"
      >
        {{ opt.label }}
      </button>
    </div>

    <div class="flex gap-1.5 ml-auto">
      <button v-for="ex in exercises" :key="ex" @click="$emit('exercise', ex)"
              class="px-2.5 py-1 text-[10px] pill-tag"
              :class="{ 'pill-tag-active': ex === current }">
        {{ ex }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  isIdle: boolean
  isPaused: boolean
  current: string
  exercises: string[]
  targetReps: number
}>()

defineEmits<{
  start: []
  stop: []
  pause: []
  exercise: [name: string]
  target: [value: number]
}>()

const targetOptions = [
  { label: '自由', value: 0 },
  { label: '5', value: 5 },
  { label: '10', value: 10 },
  { label: '15', value: 15 },
  { label: '20', value: 20 },
  { label: '30', value: 30 },
]
</script>
