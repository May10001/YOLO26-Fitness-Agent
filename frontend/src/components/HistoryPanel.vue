<template>
  <div class="flat-card p-3.5 flex-1 flex flex-col min-h-0">
    <div class="text-[10px] uppercase tracking-wider text-steel font-semibold mb-2.5">训练历史</div>
    <div v-if="loading" class="text-[10px] text-faint">加载中...</div>
    <div v-else-if="sessions.length === 0" class="text-[10px] text-faint">暂无训练记录</div>
    <div v-else class="flex-1 overflow-y-auto flex flex-col gap-1.5">
      <div v-for="s in sessions" :key="s.session_id"
           class="rounded-lg p-2.5 bg-mist border border-concrete">
        <div class="flex justify-between items-center mb-1">
          <span class="text-[11px] text-obsidian font-medium">{{ s.exercise }}</span>
          <span class="text-[9px] text-faint">{{ formatDate(s.start_time) }}</span>
        </div>
        <div class="flex gap-3 text-[10px] text-steel">
          <span>⏱ {{ fmtDuration(s.duration_seconds) }}</span>
          <span>🔢 {{ s.total_reps }}次</span>
          <span>⭐ {{ s.best_score }}分</span>
          <span class="text-faint">均{{ s.avg_score }}分</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { SessionRecord } from '../types'
import { config } from '../config'

const sessions = ref<SessionRecord[]>([])
const loading = ref(true)

async function loadHistory() {
  loading.value = true
  try {
    const res = await fetch(config.endpoints.sessions)
    const data = await res.json()
    sessions.value = data.sessions || []
  } catch { /* keep empty list */ }
  loading.value = false
}

function formatDate(iso: string): string {
  if (!iso) return ''
  // "2026-06-02T14:30:00" → "06/02 14:30"
  try {
    const d = new Date(iso)
    return `${(d.getMonth()+1).toString().padStart(2,'0')}/${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
  } catch { return iso }
}

function fmtDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

onMounted(loadHistory)
</script>
