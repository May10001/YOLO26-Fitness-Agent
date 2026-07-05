<template>
  <div v-if="debug" class="absolute inset-0 z-20 pointer-events-none">
    <!-- ============================================================ -->
    <!-- Section 1: Raw Joint Angles                                  -->
    <!-- ============================================================ -->
    <div class="absolute top-16 left-4 bg-black/80 backdrop-blur-lg border border-white/10 rounded-xl px-3.5 py-2.5 text-[10px] font-mono leading-relaxed min-w-[200px]">
      <div class="text-[9px] text-gray-500 mb-1.5 uppercase tracking-wider">📐 原始角度</div>

      <div class="flex justify-between gap-6">
        <span class="text-gray-400">左膝</span>
        <span :class="angleColor(debug.knee_left, debug.target_angle)">{{ fmt(debug.knee_left) }}°</span>
      </div>
      <div class="flex justify-between gap-6">
        <span class="text-gray-400">右膝</span>
        <span :class="angleColor(debug.knee_right, debug.target_angle)">{{ fmt(debug.knee_right) }}°</span>
      </div>
      <div class="flex justify-between gap-6 mt-1 border-t border-white/5 pt-1">
        <span class="text-gray-500">目标</span>
        <span class="text-paper">{{ debug.target_angle ?? '--' }}°</span>
      </div>
      <div class="flex justify-between gap-6">
        <span class="text-gray-500">阶段</span>
        <span class="text-emerald-400">{{ phase || '--' }}</span>
      </div>
      <div class="flex justify-between gap-6">
        <span class="text-gray-500">偏差</span>
        <span :class="deviationColor(debug.deviation)">{{ fmt(debug.deviation) }}°</span>
      </div>
      <div class="flex justify-between gap-6 mt-1 border-t border-white/5 pt-1">
        <span class="text-gray-400">左右差异</span>
        <span :class="symmetryColor(debug.knee_diff, debug.symmetry_max_diff)">
          {{ fmt(debug.knee_diff) }}°
          <span class="text-[9px] text-gray-600">/ {{ debug.symmetry_max_diff ?? '--' }}°</span>
        </span>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- Section 2: Score Breakdown                                   -->
    <!-- ============================================================ -->
    <div class="absolute top-16 right-4 bg-black/80 backdrop-blur-lg border border-white/10 rounded-xl px-3.5 py-2.5 text-[10px] font-mono leading-relaxed min-w-[220px]">
      <div class="text-[9px] text-gray-500 mb-1.5 uppercase tracking-wider">📊 评分明细</div>

      <div class="flex justify-between gap-6">
        <span class="text-gray-400">角度分</span>
        <span class="text-paper">{{ score.angle.toFixed(1) }}/40</span>
      </div>
      <div class="text-[8px] text-gray-600 pl-2 leading-tight">
        exp(-({{ fmt(debug.deviation) }}/{{ tuning.angle_tolerance }})²)×40
      </div>

      <div class="flex justify-between gap-6 mt-1">
        <span class="text-gray-400">对称分</span>
        <span class="text-paper">{{ score.symmetry.toFixed(1) }}/30</span>
      </div>
      <div class="text-[8px] text-gray-600 pl-2 leading-tight">
        (1 - {{ fmt(debug.knee_diff) }}/{{ debug.symmetry_max_diff ?? 12 }})×30
      </div>

      <div class="flex justify-between gap-6 mt-1">
        <span class="text-gray-400">时序分</span>
        <span class="text-amber-400">{{ score.temporal.toFixed(1) }}/30</span>
      </div>
      <div class="text-[8px] text-gray-600 pl-2 leading-tight">
        CV:{{ debug.temporal_rhythm_cv?.toFixed(3) }} 平滑:{{ fmt(debug.temporal_smoothness) }}
      </div>

      <div class="flex justify-between gap-6 mt-1.5 pt-1.5 border-t border-white/10 font-bold">
        <span class="text-gray-300">总分</span>
        <span :class="totalColor(score.total)">{{ score.total.toFixed(1) }}/100</span>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- Section 5: Diagnostic Snapshot (σ, trends, co-occurrence)     -->
    <!-- ============================================================ -->
    <div v-if="diag" class="absolute top-[54%] right-4 bg-black/80 backdrop-blur-lg border border-white/10 rounded-xl px-3.5 py-2.5 text-[10px] font-mono leading-relaxed max-w-[280px] pointer-events-auto">
      <div class="flex items-center justify-between mb-1.5">
        <span class="text-[9px] text-gray-500 uppercase tracking-wider">🔬 诊断快照</span>
        <button class="text-[9px] text-gray-600 hover:text-gray-400 transition-colors"
                @click="showDiagDetail = !showDiagDetail">
          {{ showDiagDetail ? '折叠' : '展开' }}
        </button>
      </div>

      <!-- Dimension diagnosis (always visible) -->
      <div class="text-[9px] leading-snug mb-1.5" :class="diagDimColor(diag.dimension_diagnosis)">
        {{ diag.dimension_diagnosis || '暂无维度诊断' }}
      </div>

      <!-- Angle trend (always visible) -->
      <div v-if="diag.angle_trend" class="flex items-center gap-1.5 text-[9px] mb-1">
        <span class="text-gray-500">趋势:</span>
        <span :class="trendColor(diag.angle_trend.direction)">{{ diag.angle_trend.direction }}</span>
        <span class="text-gray-600">(斜率 {{ diag.angle_trend.slope >= 0 ? '+' : '' }}{{ diag.angle_trend.slope.toFixed(3) }}°/帧)</span>
      </div>

      <!-- Detail section (expandable) -->
      <div v-if="showDiagDetail" class="mt-2 pt-2 border-t border-white/[0.06] space-y-2 animate-[fadeIn_0.2s_ease-out]">
        <!-- Per-joint stability -->
        <div v-if="diag.joint_deviations?.length">
          <div class="text-[8px] text-gray-600 mb-1 uppercase tracking-wider">关节稳定性 (σ)</div>
          <div class="space-y-0.5">
            <div v-for="jd in diag.joint_deviations" :key="jd.joint_name"
                 class="flex items-center justify-between gap-2">
              <span class="text-gray-400 w-10">{{ jd.joint_name }}</span>
              <span class="text-gray-300 w-10 text-right">{{ jd.current }}°</span>
              <div class="flex-1 h-1 bg-white/[0.06] rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-300"
                     :class="stabilityBarColor(jd.stability)"
                     :style="{ width: Math.min(100, (jd.std_dev / 10) * 100) + '%' }" />
              </div>
              <span class="w-12 text-right" :class="stabilityTextColor(jd.stability)">
                σ={{ jd.std_dev.toFixed(1) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Co-occurrence patterns -->
        <div v-if="diag.error_cooccurrence?.length">
          <div class="text-[8px] text-gray-600 mb-1 uppercase tracking-wider">共现模式</div>
          <div v-for="(cp, i) in diag.error_cooccurrence" :key="i"
               class="text-[9px] text-amber-300/80 leading-snug bg-amber-500/[0.06] rounded px-2 py-1 border border-amber-500/10">
            <span class="text-amber-400 font-semibold">{{ cp.errors.join(' + ') }}</span>
            <span class="text-gray-500 mx-1">→</span>
            <span class="text-gray-400">{{ cp.interpretation }}</span>
          </div>
        </div>

        <!-- Recent angle values -->
        <div v-if="diag.angle_trend?.recent_values?.length">
          <div class="text-[8px] text-gray-600 mb-0.5 uppercase tracking-wider">近5帧角度</div>
          <div class="flex gap-0.5">
            <span v-for="(v, i) in diag.angle_trend.recent_values.slice(-5)" :key="i"
                  class="px-1 py-0.5 rounded text-[8px] bg-white/[0.04] text-gray-400 font-mono">{{ v.toFixed(0) }}°</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- Section 3: Angle Trace (oscilloscope-style)                  -->
    <!-- ============================================================ -->
    <div v-if="angleHistory.length > 1" class="absolute bottom-20 left-4 right-4 bg-black/80 backdrop-blur-lg border border-white/10 rounded-xl px-3.5 py-2.5">
      <div class="text-[9px] text-gray-500 mb-1 uppercase tracking-wider">📈 角度波形 (近{{ angleHistory.length }}帧)</div>
      <div class="relative h-14 bg-black/40 rounded overflow-hidden">
        <div class="absolute left-0 right-0 border-t border-dashed border-flame/30"
             :style="{ bottom: pct(tuning.target_low) + '%' }">
          <span class="absolute -top-3 left-1 text-[8px] text-flame/50">{{ tuning.target_low }}°</span>
        </div>
        <div class="absolute left-0 right-0 border-t border-dashed border-rose/30"
             :style="{ bottom: pct(tuning.target_high) + '%' }">
          <span class="absolute -top-3 left-1 text-[8px] text-rose/50">{{ tuning.target_high }}°</span>
        </div>
        <div class="flex items-end h-full gap-[1px] px-0.5">
          <div v-for="(val, i) in angleHistory" :key="i"
               class="flex-1 min-w-[3px] rounded-t transition-all duration-150"
               :class="barColor(val)"
               :style="{ height: pct(val) + '%' }" />
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- Section 4: Parameter Tuning Sliders                           -->
    <!-- ============================================================ -->
    <div class="absolute bottom-4 left-1/2 -translate-x-1/2 w-[520px] bg-black/85 backdrop-blur-lg border border-white/15 rounded-xl px-4 py-3 pointer-events-auto">
      <div class="flex items-center justify-between mb-2">
        <span class="text-[9px] text-gray-500 uppercase tracking-wider">🎛️ 实时调参</span>
        <button
          class="text-[9px] px-2 py-0.5 rounded border border-white/10 text-gray-500 hover:text-paper hover:border-white/40 transition-colors"
          @click="resetTuning">重置默认</button>
      </div>
      <div class="grid grid-cols-5 gap-3">
        <!-- target_low -->
        <div class="flex flex-col items-center">
          <div class="flex justify-between w-full text-[8px] mb-0.5">
            <span class="text-gray-500">底部</span>
            <span class="text-flame font-mono">{{ tuning.target_low }}°</span>
          </div>
          <input type="range" :min="60" :max="120" :step="1"
                 v-model.number="tuning.target_low" @input="onSliderChange"
                 class="w-full h-1 accent-flame cursor-pointer" />
        </div>
        <!-- target_high -->
        <div class="flex flex-col items-center">
          <div class="flex justify-between w-full text-[8px] mb-0.5">
            <span class="text-gray-500">顶部</span>
            <span class="text-rose font-mono">{{ tuning.target_high }}°</span>
          </div>
          <input type="range" :min="140" :max="180" :step="1"
                 v-model.number="tuning.target_high" @input="onSliderChange"
                 class="w-full h-1 accent-rose cursor-pointer" />
        </div>
        <!-- symmetry_max_diff -->
        <div class="flex flex-col items-center">
          <div class="flex justify-between w-full text-[8px] mb-0.5">
            <span class="text-gray-500">对称</span>
            <span class="text-amber-400 font-mono">{{ tuning.symmetry_max_diff }}°</span>
          </div>
          <input type="range" :min="5" :max="35" :step="0.5"
                 v-model.number="tuning.symmetry_max_diff" @input="onSliderChange"
                 class="w-full h-1 accent-amber-400 cursor-pointer" />
        </div>
        <!-- angle_tolerance -->
        <div class="flex flex-col items-center">
          <div class="flex justify-between w-full text-[8px] mb-0.5">
            <span class="text-gray-500">容差</span>
            <span class="text-emerald-400 font-mono">{{ tuning.angle_tolerance }}</span>
          </div>
          <input type="range" :min="3" :max="25" :step="0.5"
                 v-model.number="tuning.angle_tolerance" @input="onSliderChange"
                 class="w-full h-1 accent-emerald-400 cursor-pointer" />
        </div>
        <!-- smooth_alpha -->
        <div class="flex flex-col items-center">
          <div class="flex justify-between w-full text-[8px] mb-0.5">
            <span class="text-gray-500">平滑</span>
            <span class="text-purple-400 font-mono">{{ tuning.smooth_alpha.toFixed(2) }}</span>
          </div>
          <input type="range" :min="0.1" :max="0.95" :step="0.05"
                 v-model.number="tuning.smooth_alpha" @input="onSliderChange"
                 class="w-full h-1 accent-purple-400 cursor-pointer" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, reactive } from 'vue'
import type { DebugData, ScoreData, ScoringConfig, DiagnosticSnapshotData } from '../types'

import { config } from '../config'
const API_BASE = config.apiBase

const props = defineProps<{
  debug: DebugData | null
  score: ScoreData
  phase: string
  diagnosticSnapshot?: DiagnosticSnapshotData | null
}>()

const diag = ref<DiagnosticSnapshotData | null>(null)
const showDiagDetail = ref(false)

// Watch for diagnostic snapshot from parent
watch(() => props.diagnosticSnapshot, (val) => {
  if (val) diag.value = val
})

// ---- Parameter tuning state ----
const tuning = reactive<ScoringConfig>({
  target_low: 90,
  target_high: 170,
  symmetry_max_diff: 25,
  angle_tolerance: 12.5,
  smooth_alpha: 0.7,
})

const DEFAULTS = { ...tuning }

let debounceTimer: ReturnType<typeof setTimeout> | null = null

async function fetchTuningParams() {
  try {
    const res = await fetch(`${API_BASE}/api/config/scoring`)
    if (res.ok) {
      const data = await res.json()
      Object.assign(tuning, data)
    }
  } catch { /* keep defaults */ }
}

function resetTuning() {
  Object.assign(tuning, DEFAULTS)
  sendTuningParams()
}

function onSliderChange() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(sendTuningParams, 200)
}

async function sendTuningParams() {
  try {
    await fetch(`${API_BASE}/api/config/scoring`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tuning),
    })
  } catch { /* ignore network errors */ }
}

// ---- Angle trace history (last 30 frames) ----
const angleHistory = ref<number[]>([])

watch(() => props.debug?.primary_angle, (val) => {
  if (val !== null && val !== undefined) {
    angleHistory.value.push(val)
    if (angleHistory.value.length > 30) angleHistory.value.shift()
  }
})

// ---- Helpers ----
function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return '--'
  return v.toFixed(1)
}

/** Map angle value (70–180 range) to 0–100% height */
function pct(angle: number): number {
  const lo = 60, hi = 190
  return Math.max(0, Math.min(100, ((angle - lo) / (hi - lo)) * 100))
}

// ---- Color coding ----
function angleColor(val: number | null | undefined, target: number | null | undefined): string {
  if (val == null || target == null) return 'text-gray-500'
  const d = Math.abs(val - target)
  if (d < 8) return 'text-emerald-400'
  if (d < 18) return 'text-amber-400'
  return 'text-red-400'
}

function deviationColor(dev: number | null | undefined): string {
  if (dev == null) return 'text-gray-500'
  if (dev < 8) return 'text-emerald-400'
  if (dev < 18) return 'text-amber-400'
  return 'text-red-400'
}

function symmetryColor(diff: number | null | undefined, maxDiff: number | null | undefined): string {
  if (diff == null || maxDiff == null) return 'text-gray-500'
  const ratio = diff / maxDiff
  if (ratio < 0.5) return 'text-emerald-400'
  if (ratio < 0.85) return 'text-amber-400'
  return 'text-red-400'
}

function totalColor(total: number): string {
  if (total >= 85) return 'text-emerald-400'
  if (total >= 70) return 'text-amber-400'
  return 'text-red-400'
}

function barColor(val: number): string {
  // Color the bar based on proximity to target_low (90) when low, target_high (170) when high
  // Simplified: green for mid-range (80-100 and 160-175), yellow otherwise
  if ((val >= 80 && val <= 105) || (val >= 155 && val <= 180)) return 'bg-emerald-500/70'
  if ((val >= 70 && val <= 115) || (val >= 145 && val <= 185)) return 'bg-amber-500/60'
  return 'bg-red-500/50'
}

// ---- Diagnostic snapshot helpers ----
function diagDimColor(text: string): string {
  if (!text) return 'text-gray-500'
  if (text.includes('均衡') || text.includes('无明显短板')) return 'text-emerald-400'
  if (text.includes('严重不足') || text.includes('基础动作模式')) return 'text-red-400'
  if (text.includes('明显偏低') || text.includes('重点改进')) return 'text-amber-400'
  return 'text-gray-300'
}

function trendColor(direction: string): string {
  if (direction === '改善中') return 'text-emerald-400'
  if (direction === '恶化中') return 'text-red-400'
  return 'text-gray-400'
}

function stabilityBarColor(stability: string): string {
  if (stability === '稳定') return 'bg-emerald-500'
  if (stability === '轻微波动') return 'bg-amber-500'
  return 'bg-red-500'
}

function stabilityTextColor(stability: string): string {
  if (stability === '稳定') return 'text-emerald-400'
  if (stability === '轻微波动') return 'text-amber-400'
  return 'text-red-400'
}
</script>
