<template>
  <div class="glow-card rounded-[14px] p-3.5">
    <div class="flex justify-between items-center mb-2.5">
      <span class="text-[10px] uppercase tracking-wider text-flame/70 font-semibold">关节角度</span>
      <span class="text-[9px] text-gray-600">{{ summaryText }}</span>
    </div>
    <div v-if="!joints || joints.length === 0" class="text-[10px] text-gray-600">等待数据...</div>
    <div v-else class="flex flex-col gap-1">
      <div v-for="j in joints" :key="j.key"
           class="flex items-center gap-2 text-[10px]">
        <span class="w-10 text-right text-gray-400 shrink-0">{{ j.name }}</span>
        <div class="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
          <div class="h-full rounded-full transition-all duration-500"
               :class="barColor(j.severity)"
               :style="{ width: Math.min(j.deviation_ratio * 100, 100) + '%' }" />
        </div>
        <span class="w-10 text-right shrink-0"
              :class="textColor(j.severity)">{{ j.user_avg }}°</span>
        <span class="w-5 text-center shrink-0"
              :class="dotColor(j.severity)">{{ severityIcon(j.severity) }}</span>
      </div>
    </div>
    <!-- Legend -->
    <div class="flex gap-3 mt-2 pt-2 border-t border-white/[0.05] text-[8px] text-gray-500">
      <span>🟢 标准</span><span>🟠 偏差</span><span>🔴 偏离</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface JointDeviation {
  key: string
  name: string
  user_avg: number
  standard_mid: number
  deviation: number
  deviation_ratio: number
  severity: 'good' | 'warning' | 'bad'
}

const props = defineProps<{
  joints: JointDeviation[] | null
}>()

const summaryText = computed(() => {
  if (!props.joints) return ''
  const good = props.joints.filter(j => j.severity === 'good').length
  const warn = props.joints.filter(j => j.severity === 'warning').length
  const bad = props.joints.filter(j => j.severity === 'bad').length
  const parts = []
  if (good) parts.push(`${good}标准`)
  if (warn) parts.push(`${warn}偏差`)
  if (bad) parts.push(`${bad}偏离`)
  return parts.join(' · ')
})

function barColor(s: string) {
  if (s === 'good') return 'bg-success/70'
  if (s === 'warning') return 'bg-amber-400/70'
  return 'bg-danger/70'
}
function textColor(s: string) {
  if (s === 'good') return 'text-success'
  if (s === 'warning') return 'text-amber-400'
  return 'text-danger'
}
function dotColor(s: string) {
  return ''
}
function severityIcon(s: string) {
  if (s === 'good') return '●'
  if (s === 'warning') return '●'
  return '●'
}
</script>
