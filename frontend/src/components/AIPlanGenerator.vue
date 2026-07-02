<template>
  <div class="glow-card rounded-[14px] p-4 space-y-3">
    <div class="text-[10px] uppercase tracking-wider text-flame/80 font-semibold">AI Plan</div>

    <!-- User request input -->
    <div>
      <textarea v-model="userRequest" rows="2"
                placeholder="描述你想怎么练，AI 会帮你生成一份完整的训练计划。&#10;例如：30分钟腿部训练，中等强度"
                class="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-flame/40 transition-colors resize-none placeholder:text-gray-600" />
    </div>

    <!-- Generate button -->
    <button @click="generatePlan" :disabled="generating || !userRequest.trim()"
            class="w-full py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-flame to-rose text-white shadow-[0_0_20px_rgba(255,106,0,0.2)] hover:shadow-[0_0_30px_rgba(255,106,0,0.4)] transition-all duration-300 disabled:opacity-40">
      {{ generating ? 'AI 正在为你设计训练方案...' : '生成 AI 训练计划' }}
    </button>

    <!-- Error -->
    <div v-if="errorMsg" class="text-[10px] text-red-400 text-center">{{ errorMsg }}</div>

    <!-- Generated plan -->
    <div v-if="plan" class="space-y-3">
      <!-- Plan header -->
      <div class="bg-white/[0.03] rounded-xl p-3 border border-flame/20">
        <div class="flex justify-between items-center">
          <div>
            <div class="text-sm font-bold text-white">{{ plan.plan_name }}</div>
            <div class="text-[9px] text-gray-500 mt-0.5">约 {{ plan.total_duration_minutes }} 分钟</div>
          </div>
          <button @click="$emit('start', flatSteps)"
                  class="px-4 py-2 rounded-lg text-[11px] font-bold bg-gradient-to-r from-flame to-rose text-white shadow-[0_0_15px_rgba(255,106,0,0.3)]">
            开始训练
          </button>
        </div>
      </div>

      <!-- Warmup -->
      <div v-if="plan.warmup && plan.warmup.length" class="space-y-1">
        <div class="text-[9px] text-emerald-400 font-semibold uppercase tracking-wider">热身</div>
        <div v-for="(s, i) in plan.warmup" :key="'w'+i"
             class="bg-white/[0.02] rounded-lg px-3 py-2 flex justify-between items-center border border-white/[0.05]">
          <span class="text-[11px] text-gray-300">{{ s.exercise }}</span>
          <span class="text-[10px] text-gray-500">{{ s.reps }} reps</span>
        </div>
      </div>

      <!-- Main blocks -->
      <div v-for="(block, bi) in plan.blocks" :key="'b'+bi" class="space-y-1">
        <div class="text-[9px] text-flame font-semibold uppercase tracking-wider">
          {{ block.name }} <span v-if="block.rounds > 1" class="text-gray-500">×{{ block.rounds }}</span>
        </div>
        <div v-for="(ex, ei) in block.exercises" :key="'e'+ei"
             class="bg-white/[0.02] rounded-lg px-3 py-2.5 border border-white/[0.05]">
          <div class="flex justify-between items-center">
            <span class="text-[11px] text-white font-medium">{{ ex.exercise }}</span>
            <span class="text-[10px] text-gray-500">{{ ex.sets }}×{{ ex.reps }}</span>
          </div>
          <div v-if="ex.notes" class="text-[9px] text-gray-600 mt-1">{{ ex.notes }}</div>
          <div class="flex gap-3 mt-1 text-[9px] text-gray-600">
            <span v-if="ex.tempo">节奏 {{ ex.tempo }}</span>
            <span>休息 {{ ex.rest_seconds }}s</span>
          </div>
        </div>
      </div>

      <!-- Cooldown -->
      <div v-if="plan.cooldown && plan.cooldown.length" class="space-y-1">
        <div class="text-[9px] text-blue-400 font-semibold uppercase tracking-wider">整理</div>
        <div v-for="(s, i) in plan.cooldown" :key="'c'+i"
             class="bg-white/[0.02] rounded-lg px-3 py-2 flex justify-between items-center border border-white/[0.05]">
          <span class="text-[11px] text-gray-300">{{ s.exercise }}</span>
          <span class="text-[10px] text-gray-500">{{ s.duration_seconds || s.reps }}{{ s.duration_seconds ? 's' : ' reps' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { AIPlan, PlanStep } from '../types'
import { config } from '../config'

const props = defineProps<{
  profile: Record<string, unknown>
}>()

const emit = defineEmits<{
  start: [steps: PlanStep[]]
}>()

const userRequest = ref('')
const generating = ref(false)
const errorMsg = ref('')
const plan = ref<AIPlan | null>(null)

// Flatten plan into sequential steps for PlanRunner
const flatSteps = ref<PlanStep[]>([])

async function generatePlan() {
  if (!userRequest.value.trim()) return
  generating.value = true
  errorMsg.value = ''
  plan.value = null

  try {
    const res = await fetch(config.endpoints.aiPlanGenerate, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: props.profile,
        user_request: userRequest.value.trim(),
      }),
    })
    const data = await res.json()
    if (data.error) {
      errorMsg.value = data.error
      return
    }
    if (data.plan) {
      plan.value = data.plan
      // Flatten: warmup → blocks (expand rounds) → cooldown
      const steps: PlanStep[] = []
      for (const s of (data.plan.warmup || [])) steps.push({ ...s, sets: 1 })
      for (const block of (data.plan.blocks || [])) {
        for (let r = 0; r < (block.rounds || 1); r++) {
          for (const ex of block.exercises) steps.push(ex)
        }
      }
      for (const s of (data.plan.cooldown || [])) steps.push({ ...s, sets: 1 })
      flatSteps.value = steps
    }
  } catch (e) {
    errorMsg.value = '网络错误，请重试'
  } finally {
    generating.value = false
  }
}
</script>
