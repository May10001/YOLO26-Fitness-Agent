<template>
  <div class="flat-card p-4 space-y-3">
    <div class="text-[10px] uppercase tracking-wider text-steel font-semibold">AI Plan</div>

    <!-- User request input -->
    <div>
      <textarea v-model="userRequest" rows="2"
                placeholder="描述你想怎么练，AI 会帮你生成一份完整的训练计划。&#10;例如：30分钟腿部训练，中等强度"
                class="w-full bg-mist border border-concrete rounded-lg px-3 py-2 text-xs text-obsidian outline-none focus:border-steel transition-colors resize-none placeholder:text-faint" />
    </div>

    <!-- Generate button -->
    <button @click="generatePlan" :disabled="generating || !userRequest.trim()"
            class="pill-btn w-full py-2.5 text-xs font-bold">
      {{ generating ? 'AI 正在为你设计训练方案...' : '生成 AI 训练计划' }}
    </button>

    <!-- Error -->
    <div v-if="errorMsg" class="text-[10px] text-danger text-center">{{ errorMsg }}</div>

    <!-- Generated plan -->
    <div v-if="plan" class="space-y-3">
      <!-- Plan header -->
      <div class="bg-mist rounded-xl p-3 border border-concrete">
        <div class="flex justify-between items-center">
          <div>
            <div class="text-sm font-bold text-obsidian">{{ plan.plan_name }}</div>
            <div class="text-[9px] text-faint mt-0.5">约 {{ plan.total_duration_minutes }} 分钟</div>
          </div>
          <button @click="$emit('start', flatSteps)"
                  class="pill-btn px-4 py-2 text-[11px] font-bold">
            开始训练
          </button>
        </div>
      </div>

      <!-- Warmup -->
      <div v-if="plan.warmup && plan.warmup.length" class="space-y-1">
        <div class="text-[9px] text-steel font-semibold uppercase tracking-wider">热身</div>
        <div v-for="(s, i) in plan.warmup" :key="'w'+i"
             class="bg-paper rounded-lg px-3 py-2 flex justify-between items-center border border-concrete">
          <span class="text-[11px] text-obsidian">{{ s.exercise }}</span>
          <span class="text-[10px] text-faint">{{ s.reps }} reps</span>
        </div>
      </div>

      <!-- Main blocks -->
      <div v-for="(block, bi) in plan.blocks" :key="'b'+bi" class="space-y-1">
        <div class="text-[9px] text-steel font-semibold uppercase tracking-wider">
          {{ block.name }} <span v-if="block.rounds > 1" class="text-faint">×{{ block.rounds }}</span>
        </div>
        <div v-for="(ex, ei) in block.exercises" :key="'e'+ei"
             class="bg-paper rounded-lg px-3 py-2.5 border border-concrete">
          <div class="flex justify-between items-center">
            <span class="text-[11px] text-obsidian font-medium">{{ ex.exercise }}</span>
            <span class="text-[10px] text-faint">{{ ex.sets }}×{{ ex.reps }}</span>
          </div>
          <div v-if="ex.notes" class="text-[9px] text-faint mt-1">{{ ex.notes }}</div>
          <div class="flex gap-3 mt-1 text-[9px] text-faint">
            <span v-if="ex.tempo">节奏 {{ ex.tempo }}</span>
            <span>休息 {{ ex.rest_seconds }}s</span>
          </div>
        </div>
      </div>

      <!-- Cooldown -->
      <div v-if="plan.cooldown && plan.cooldown.length" class="space-y-1">
        <div class="text-[9px] text-steel font-semibold uppercase tracking-wider">整理</div>
        <div v-for="(s, i) in plan.cooldown" :key="'c'+i"
             class="bg-paper rounded-lg px-3 py-2 flex justify-between items-center border border-concrete">
          <span class="text-[11px] text-obsidian">{{ s.exercise }}</span>
          <span class="text-[10px] text-faint">{{ s.duration_seconds || s.reps }}{{ s.duration_seconds ? 's' : ' reps' }}</span>
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

  // --- Try AI generation first ---
  let aiFailed = false
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
    if (data.plan) {
      applyPlan(data.plan)
      return
    }
    // AI generation returned an error — mark for fallback
    if (data.error) {
      aiFailed = true
      console.log('[AIPlan] AI generation failed, trying rule-based fallback:', data.error)
    }
  } catch (e) {
    aiFailed = true
    console.log('[AIPlan] AI generation network error, trying rule-based fallback:', e)
  }

  // --- Fallback: rule-based plan generator ---
  if (aiFailed) {
    try {
      const res = await fetch(config.endpoints.planGenerate, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(props.profile),
      })
      const data = await res.json()
      if (data.error) {
        errorMsg.value = 'AI 计划生成失败，规则引擎也未能生成计划。请检查后端服务。'
        return
      }
      // Convert WeeklyPlan format to AIPlan format
      const converted = convertWeeklyToAIPlan(data)
      if (converted) {
        applyPlan(converted)
        errorMsg.value = ''  // clear any previous AI error
      } else {
        errorMsg.value = '规则引擎返回的计划格式无法解析。'
      }
    } catch {
      errorMsg.value = 'AI 计划生成和规则引擎均不可用，请检查后端服务。'
    }
  }

  generating.value = false
}

function applyPlan(aiPlan: AIPlan) {
  plan.value = aiPlan
  // Flatten: warmup → blocks (expand rounds) → cooldown
  const steps: PlanStep[] = []
  for (const s of (aiPlan.warmup || [])) steps.push({ ...s, sets: 1 })
  for (const block of (aiPlan.blocks || [])) {
    for (let r = 0; r < (block.rounds || 1); r++) {
      for (const ex of block.exercises) steps.push(ex)
    }
  }
  for (const s of (aiPlan.cooldown || [])) steps.push({ ...s, sets: 1 })
  flatSteps.value = steps
  generating.value = false
}

/** Convert rule-based WeeklyPlan to AI-style AIPlan format. */
function convertWeeklyToAIPlan(weekly: Record<string, unknown>): AIPlan | null {
  const days = weekly.days as Array<Record<string, unknown>> | undefined
  if (!days || days.length === 0) return null

  // Use the first training day as the plan content
  const firstDay = days[0]
  const exercises = (firstDay.exercises || []) as Array<Record<string, unknown>>

  // Warmup: first 1-2 exercises if they are cardio-like
  const cardioLike = new Set(['开合跳', '高抬腿'])
  const warmup: PlanStep[] = []
  const mainExercises: PlanStep[] = []
  const cooldown: PlanStep[] = []

  for (const ex of exercises) {
    const name = (ex.name || '深蹲') as string
    const step: PlanStep = {
      exercise: name,
      reps: (ex.reps || 10) as number,
      sets: (ex.sets || 3) as number,
      rest_seconds: (ex.rest_seconds || 60) as number,
      notes: (ex.notes || '') as string,
    }
    if (cardioLike.has(name)) {
      warmup.push(step)
    } else if (name === '平板支撑') {
      cooldown.push({ ...step, duration_seconds: 30 })
    } else {
      mainExercises.push(step)
    }
  }

  // If no cardio-like exercises, take first exercise as warmup with reduced reps
  if (warmup.length === 0 && mainExercises.length > 0) {
    const first = mainExercises.shift()!
    warmup.push({ ...first, reps: Math.min(first.reps, 15), sets: 1, rest_seconds: 30 })
  }

  const goalMap: Record<string, string> = {
    strength: 'strength', weight_loss: 'weight_loss',
    hypertrophy: 'strength', endurance: 'endurance', general: 'general',
  }
  const goal = (weekly.goal as string) || 'general'

  return {
    plan_name: `${firstDay.focus || '训练'}计划`,
    plan_type: goalMap[goal] || 'general',
    total_duration_minutes: exercises.length * 5 + 10,
    warmup,
    blocks: [{ name: firstDay.focus as string || '主训练', rounds: 1, exercises: mainExercises }],
    cooldown,
  }
}
</script>
