<template>
  <Transition name="summary">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md">
      <div class="w-[520px] max-h-[90vh] overflow-y-auto rounded-3xl bg-[#111] border border-flame/25 shadow-[0_0_100px_rgba(255,106,0,0.15)] p-8">
        <!-- Header -->
        <div class="text-center mb-7">
          <div class="text-[10px] uppercase tracking-[6px] text-flame/60 mb-2">Training Complete</div>
          <div class="text-2xl font-extrabold text-white">{{ data.exercise }}</div>
          <div class="text-sm text-gray-500 mt-1">{{ data.duration }}</div>
        </div>

        <!-- Core stats grid -->
        <div class="grid grid-cols-3 gap-3 mb-7">
          <div class="bg-white/[0.03] rounded-2xl p-4 text-center border border-white/[0.06]">
            <div class="text-4xl font-extrabold gradient-text">{{ data.totalReps }}</div>
            <div class="text-[9px] text-gray-500 mt-1.5 uppercase tracking-[2px]">总次数</div>
            <div v-if="data.targetReps > 0" class="text-[10px] text-gray-600 mt-0.5">目标 {{ data.targetReps }}</div>
          </div>
          <div class="bg-white/[0.03] rounded-2xl p-4 text-center border border-white/[0.06]">
            <div class="text-4xl font-extrabold text-flame">{{ data.bestScore.toFixed(0) }}</div>
            <div class="text-[9px] text-gray-500 mt-1.5 uppercase tracking-[2px]">最佳得分</div>
          </div>
          <div class="bg-white/[0.03] rounded-2xl p-4 text-center border border-white/[0.06]">
            <div class="text-4xl font-extrabold text-white">{{ data.avgScore.toFixed(0) }}</div>
            <div class="text-[9px] text-gray-500 mt-1.5 uppercase tracking-[2px]">平均得分</div>
          </div>
        </div>

        <!-- Score breakdown bars -->
        <div class="mb-7">
          <div class="text-[10px] text-gray-500 uppercase tracking-[3px] mb-3">Score Breakdown</div>
          <div class="space-y-2.5">
            <div class="flex items-center gap-3">
              <span class="w-10 text-[10px] text-gray-400 text-right">角度</span>
              <div class="flex-1 h-2.5 rounded-full bg-white/[0.05] overflow-hidden">
                <div class="h-full rounded-full bg-flame transition-all duration-700"
                     :style="{ width: (data.finalScore.angle / 40 * 100) + '%' }" />
              </div>
              <span class="w-8 text-[10px] text-gray-300 text-right font-bold">{{ data.finalScore.angle.toFixed(0) }}</span>
              <span class="text-[9px] text-gray-600">/40</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="w-10 text-[10px] text-gray-400 text-right">时序</span>
              <div class="flex-1 h-2.5 rounded-full bg-white/[0.05] overflow-hidden">
                <div class="h-full rounded-full bg-rose transition-all duration-700"
                     :style="{ width: (data.finalScore.temporal / 30 * 100) + '%' }" />
              </div>
              <span class="w-8 text-[10px] text-gray-300 text-right font-bold">{{ data.finalScore.temporal.toFixed(0) }}</span>
              <span class="text-[9px] text-gray-600">/30</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="w-10 text-[10px] text-gray-400 text-right">对称</span>
              <div class="flex-1 h-2.5 rounded-full bg-white/[0.05] overflow-hidden">
                <div class="h-full rounded-full bg-flame transition-all duration-700"
                     :style="{ width: (data.finalScore.symmetry / 30 * 100) + '%' }" />
              </div>
              <span class="w-8 text-[10px] text-gray-300 text-right font-bold">{{ data.finalScore.symmetry.toFixed(0) }}</span>
              <span class="text-[9px] text-gray-600">/30</span>
            </div>
          </div>
        </div>

        <!-- Error ranking -->
        <div v-if="data.errors.length > 0" class="mb-7">
          <div class="text-[10px] text-gray-500 uppercase tracking-[3px] mb-3">Errors Detected</div>
          <div class="space-y-2">
            <div v-for="(err, i) in sortedErrors" :key="err.name"
                 class="flex items-center gap-3 p-3 rounded-xl"
                 :class="err.severity >= 2
                   ? 'bg-red-500/[0.08] border border-red-500/[0.2]'
                   : 'bg-white/[0.02] border border-white/[0.05]'">
              <span class="text-xl font-extrabold w-7 text-center"
                    :class="i === 0 ? 'text-flame' : 'text-gray-600'">{{ i + 1 }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-semibold text-gray-200">{{ err.name }}</span>
                  <span class="px-1.5 py-0.5 rounded text-[9px] font-bold"
                        :class="err.severity >= 3
                          ? 'bg-red-500/20 text-red-400'
                          : err.severity >= 2
                            ? 'bg-amber-500/20 text-amber-400'
                            : 'bg-gray-500/20 text-gray-400'">
                    Lv{{ err.severity }}
                  </span>
                </div>
                <div class="text-[10px] text-gray-500 truncate mt-0.5">{{ err.suggestion }}</div>
              </div>
              <div class="text-2xl font-extrabold text-gray-500 tabular-nums">{{ err.count }}</div>
              <div class="text-[9px] text-gray-600">次</div>
            </div>
          </div>
        </div>

        <!-- No errors -->
        <div v-else class="mb-7 p-5 rounded-2xl bg-emerald-500/[0.06] border border-emerald-500/[0.2] text-center">
          <div class="text-emerald-400 font-bold text-base">动作完美</div>
          <div class="text-[11px] text-gray-500 mt-1">本次训练未检测到任何错误，继续保持！</div>
        </div>

        <!-- Action button -->
        <button @click="$emit('close')"
                class="w-full py-3 rounded-2xl text-sm font-bold
                       bg-gradient-to-r from-flame to-rose text-white
                       shadow-[0_0_30px_rgba(255,106,0,0.3)]
                       hover:shadow-[0_0_50px_rgba(255,106,0,0.5)]
                       transition-all duration-300">
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
