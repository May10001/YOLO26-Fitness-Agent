<template>
  <Transition name="summary">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md">
      <div class="w-[520px] max-h-[90vh] overflow-y-auto bg-paper border border-concrete p-8">
        <!-- Header -->
        <div class="text-center mb-7">
          <div class="text-[10px] uppercase tracking-[6px] text-steel mb-2">Training Complete</div>
          <div class="text-2xl font-display font-semibold text-white">{{ data.exercise }}</div>
          <div class="text-sm text-steel mt-1">{{ data.duration }}</div>
        </div>

        <!-- Core stats grid -->
        <div class="grid grid-cols-3 gap-3 mb-7">
          <div class="mist-card p-4 text-center">
            <div class="text-4xl font-display font-semibold text-white">{{ data.totalReps }}</div>
            <div class="text-[9px] text-steel mt-1.5 uppercase tracking-[2px]">总次数</div>
            <div v-if="data.targetReps > 0" class="text-[10px] text-faint mt-0.5">目标 {{ data.targetReps }}</div>
          </div>
          <div class="mist-card p-4 text-center">
            <div class="text-4xl font-display font-semibold text-white">{{ data.bestScore.toFixed(0) }}</div>
            <div class="text-[9px] text-steel mt-1.5 uppercase tracking-[2px]">最佳得分</div>
          </div>
          <div class="mist-card p-4 text-center">
            <div class="text-4xl font-display font-semibold text-white">{{ data.avgScore.toFixed(0) }}</div>
            <div class="text-[9px] text-steel mt-1.5 uppercase tracking-[2px]">平均得分</div>
          </div>
        </div>

        <!-- Score breakdown bars -->
        <div class="mb-7">
          <div class="text-[10px] text-steel uppercase tracking-[3px] mb-3">Score Breakdown</div>
          <div class="space-y-2.5">
            <div class="flex items-center gap-3">
              <span class="w-10 text-[10px] text-steel text-right">角度</span>
              <div class="flex-1 h-2.5 rounded-full bg-concrete overflow-hidden">
                <div class="h-full rounded-full bg-flame transition-all duration-700"
                     :style="{ width: (data.finalScore.angle / 40 * 100) + '%' }" />
              </div>
              <span class="w-8 text-[10px] text-white text-right font-medium">{{ data.finalScore.angle.toFixed(0) }}</span>
              <span class="text-[9px] text-faint">/40</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="w-10 text-[10px] text-steel text-right">时序</span>
              <div class="flex-1 h-2.5 rounded-full bg-concrete overflow-hidden">
                <div class="h-full rounded-full bg-flame transition-all duration-700"
                     :style="{ width: (data.finalScore.temporal / 30 * 100) + '%' }" />
              </div>
              <span class="w-8 text-[10px] text-white text-right font-medium">{{ data.finalScore.temporal.toFixed(0) }}</span>
              <span class="text-[9px] text-faint">/30</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="w-10 text-[10px] text-steel text-right">对称</span>
              <div class="flex-1 h-2.5 rounded-full bg-concrete overflow-hidden">
                <div class="h-full rounded-full bg-flame transition-all duration-700"
                     :style="{ width: (data.finalScore.symmetry / 30 * 100) + '%' }" />
              </div>
              <span class="w-8 text-[10px] text-white text-right font-medium">{{ data.finalScore.symmetry.toFixed(0) }}</span>
              <span class="text-[9px] text-faint">/30</span>
            </div>
          </div>
        </div>

        <!-- Key frames gallery -->
        <div v-if="data.frames && data.frames.length > 0" class="mb-7">
          <div class="text-[10px] text-steel uppercase tracking-[3px] mb-3">关键画面 ({{ data.frames.length }})</div>
          <div class="grid grid-cols-3 gap-2">
            <div v-for="(f, fi) in data.frames" :key="fi"
                 class="relative bg-mist border border-concrete overflow-hidden group">
              <img :src="'data:image/jpeg;base64,' + f.image"
                   class="w-full h-28 object-cover" />
              <div class="absolute bottom-0 left-0 right-0 px-2 py-1 text-[8px] font-medium"
                   :class="f.type === 'error'
                     ? 'bg-red-500/80 text-white'
                     : 'bg-emerald-500/80 text-white'">
                {{ f.type === 'error' ? '⚠' : '⭐' }} {{ f.label }}
              </div>
            </div>
          </div>
        </div>

        <!-- Error ranking -->
        <div v-if="data.errors.length > 0" class="mb-7">
          <div class="text-[10px] text-steel uppercase tracking-[3px] mb-3">Errors Detected</div>
          <div class="space-y-2">
            <div v-for="(err, i) in sortedErrors" :key="err.name"
                 class="flex items-center gap-3 p-3 border"
                 :class="err.severity >= 2
                   ? 'bg-red-500/[0.06] border-red-500/30'
                   : 'bg-mist border-concrete'">
              <span class="text-xl font-display font-semibold w-7 text-center"
                    :class="i === 0 ? 'text-white' : 'text-faint'">{{ i + 1 }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-white">{{ err.name }}</span>
                  <span class="px-1.5 py-0.5 rounded text-[9px] font-medium"
                        :class="err.severity >= 3
                          ? 'bg-red-500/15 text-red-500'
                          : err.severity >= 2
                            ? 'bg-amber-500/15 text-amber-600'
                            : 'bg-concrete text-steel'">
                    Lv{{ err.severity }}
                  </span>
                </div>
                <div class="text-[10px] text-steel truncate mt-0.5">{{ err.suggestion }}</div>
              </div>
              <div class="text-2xl font-display font-semibold text-steel tabular-nums">{{ err.count }}</div>
              <div class="text-[9px] text-faint">次</div>
            </div>
          </div>
        </div>

        <!-- No errors -->
        <div v-else class="mb-7 p-5 bg-success/[0.08] border border-success/40 text-center">
          <div class="text-success font-medium text-base">动作完美</div>
          <div class="text-[11px] text-steel mt-1">本次训练未检测到任何错误，继续保持！</div>
        </div>

        <!-- Action button -->
        <button @click="$emit('close')"
                class="pill-btn w-full py-3 text-sm">
          继续训练
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SummaryData } from '../types'

const props = defineProps<{
  visible: boolean
  data: SummaryData
}>()

defineEmits<{ close: [] }>()

const sortedErrors = computed(() => {
  return [...props.data.errors].sort((a, b) => b.count - a.count)
})
</script>

<style scoped>
.summary-enter-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.summary-leave-active { transition: all 0.25s ease-in; }
.summary-enter-from { opacity: 0; }
.summary-enter-from > div { transform: scale(0.92) translateY(20px); }
.summary-leave-to { opacity: 0; }
.summary-leave-to > div { transform: scale(0.95); }
</style>
