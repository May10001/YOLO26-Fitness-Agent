<template>
  <div class="h-12 rounded-xl bg-white/[0.02] border border-white/[0.05] flex items-center gap-2 px-3.5">
    <button v-if="isIdle" @click="$emit('start')" class="btn-primary px-5 py-2 text-[11px]">开始训练</button>
    <template v-else>
      <button @click="$emit('stop')" class="px-4 py-2 rounded-lg text-[11px] font-semibold bg-danger/[0.12] border border-danger/[0.25] text-danger">停止</button>
      <button @click="$emit('pause')" class="px-4 py-2 rounded-lg text-[11px] bg-white/[0.06] border border-white/10 text-gray-400">
        {{ isPaused ? '继续' : '暂停' }}
      </button>
    </template>

    <!-- Target rep selector -->
    <div class="flex items-center gap-1 ml-2">
      <span class="text-[9px] text-gray-600 mr-1">目标</span>
      <button
        v-for="opt in targetOptions" :key="opt.value"
        @click="$emit('target', opt.value)"
        class="px-2 py-1 rounded-md text-[10px] border transition-colors"
        :class="opt.value === targetReps
          ? 'bg-flame/20 border-flame/40 text-flame font-semibold'
          : 'border-white/[0.07] text-gray-500 hover:text-gray-300'"
      >
        {{ opt.label }}
      </button>
    </div>

    <div class="flex gap-1.5 ml-auto">
      <button v-for="ex in exercises" :key="ex" @click="$emit('exercise', ex)"
              class="px-2.5 py-1 rounded-lg text-[10px] border transition-colors"
              :class="ex === current
                ? 'bg-gradient-to-r from-flame/20 to-rose/10 border-flame/30 text-flame font-semibold'
                : 'border-white/[0.07] text-gray-600'">
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
