<template>
  <div class="flat-card p-3.5">
    <div class="flex justify-between items-center mb-2.5">
      <span class="text-[10px] uppercase tracking-wider text-steel font-medium">Correction</span>
      <span class="text-[9px] text-steel">{{ errors.length }} 个问题 · {{ score.total.toFixed(0) }} 分</span>
    </div>
    <div v-if="errors.length === 0 && score.total < 80" class="text-[10px] text-steel">暂无纠错信息</div>
    <div v-for="err in errors" :key="err.name"
         class="flex items-start gap-2.5 p-2.5 mb-1.5 border"
         :class="severityClass(err.severity).container">
      <div class="w-2 h-2 rounded-full mt-[3px] shrink-0"
           :class="severityClass(err.severity).dot" />
      <div>
        <div class="text-[11px] text-obsidian font-medium">{{ err.name }}</div>
        <div v-if="err.message" class="text-[10px] text-steel mt-0.5">{{ err.message }}</div>
        <div class="text-[10px] text-faint mt-0.5">{{ err.suggestion }}</div>
      </div>
    </div>
    <div v-if="errors.length === 0 && score.total >= 80"
         class="flex items-start gap-2.5 p-2.5 border border-success/40 bg-success/[0.08]">
      <div class="w-2 h-2 rounded-full bg-success mt-[3px] shrink-0" />
      <div>
        <div class="text-[11px] text-obsidian font-medium">动作良好</div>
        <div class="text-[10px] text-steel mt-0.5">继续保持当前动作质量</div>
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
      container: 'bg-danger/[0.06] border-danger/40',
      dot: 'bg-danger',
    }
  }
  if (sev === 2) {
    return {
      container: 'bg-amber-500/[0.06] border-amber-500/40',
      dot: 'bg-amber-500',
    }
  }
  return {
    container: 'bg-mist border-concrete',
    dot: 'bg-steel',
  }
}
</script>
