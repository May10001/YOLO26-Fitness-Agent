<template>
  <div class="glow-card rounded-[14px] p-3.5">
    <div class="text-[10px] uppercase tracking-wider text-flame/70 font-semibold mb-2.5">Correction</div>
    <div v-if="errors.length === 0 && score.total < 80" class="text-[10px] text-gray-600">暂无纠错信息</div>
    <div v-for="err in errors" :key="err.name"
         class="flex items-start gap-2.5 p-2.5 rounded-lg bg-danger/[0.06] border border-danger/[0.15] mb-1.5">
      <div class="w-2 h-2 rounded-full bg-danger shadow-[0_0_10px_rgba(255,77,77,0.6)] mt-[3px] shrink-0" />
      <div>
        <div class="text-[11px] text-gray-100 font-medium">{{ err.name }}</div>
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
</script>
