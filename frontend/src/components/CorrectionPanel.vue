<template>
  <div class="glow-card rounded-[14px] p-3.5">
    <div class="flex justify-between items-center mb-2.5">
      <span class="text-[10px] uppercase tracking-wider text-flame/70 font-semibold">Correction</span>
      <span class="text-[9px] text-gray-600">{{ errors.length }} 个问题 · {{ score.total.toFixed(0) }} 分</span>
    </div>
    <div v-if="errors.length === 0 && score.total < 80" class="text-[10px] text-gray-600">暂无纠错信息</div>
    <div v-for="err in errors" :key="err.name"
         class="flex items-start gap-2.5 p-2.5 rounded-lg mb-1.5"
         :class="severityClass(err.severity).container">
      <div class="w-2 h-2 rounded-full mt-[3px] shrink-0"
           :class="severityClass(err.severity).dot" />
      <div>
        <div class="text-[11px] text-gray-100 font-medium">{{ err.name }}</div>
        <div v-if="err.message" class="text-[10px] text-gray-400 mt-0.5">{{ err.message }}</div>
        <div class="text-[10px] text-gray-500 mt-0.5">{{ err.suggestion }}</div>
      </div>
    </div>
    <div v-if="errors.length === 0 && score.total >= 80"
         class="flex items-start gap-2.5 p-2.5 rounded-lg bg-success/[0.04] border border-success/[0.12]">
      <div class="w-2 h-2 rounded-full bg-success shadow-[0_0_8px_rgba(56,239,125,0.5)] mt-[3px] shrink-0" />
      <div>
        <div class="text-[11px] text-gray-100 font-medium">动作良好</div>
        <div class="text-[10px] text-gray-500 mt-0.5">继续保持当前动作质量</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ErrorData, ScoreData } from '../types'
defineProps<{ errors: ErrorData[]; score: ScoreData }>()

function severityClass(s: number | undefined) {
  const sev = s ?? 1
  if (sev >= 3) {
    return {
      container: 'bg-danger/[0.08] border border-danger/[0.2]',
      dot: 'bg-danger shadow-[0_0_12px_rgba(255,77,77,0.7)]',
    }
  }
  if (sev === 2) {
    return {
      container: 'bg-amber-500/[0.08] border border-amber-500/[0.2]',
      dot: 'bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.6)]',
    }
  }
  return {
    container: 'bg-white/[0.03] border border-white/[0.06]',
    dot: 'bg-gray-500 shadow-[0_0_6px_rgba(156,163,175,0.4)]',
  }
}
</script>
