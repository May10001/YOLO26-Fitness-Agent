<template>
  <div class="glow-card rounded-[14px] p-3.5 flex-1 flex flex-col min-h-0">
    <div class="text-[10px] uppercase tracking-wider text-flame/70 font-semibold mb-2.5">训练计划</div>
    <div class="flex-1 overflow-y-auto flex flex-col gap-2">
      <!-- Profile form -->
      <div class="grid grid-cols-2 gap-1.5">
        <input v-model="profile.name" placeholder="姓名" class="input-mini" />
        <input v-model.number="profile.age" type="number" placeholder="年龄" class="input-mini" />
        <input v-model.number="profile.weight_kg" type="number" placeholder="体重(kg)" class="input-mini" />
        <input v-model.number="profile.height_cm" type="number" placeholder="身高(cm)" class="input-mini" />
        <select v-model="profile.fitness_level" class="input-mini">
          <option value="beginner">初级</option>
          <option value="intermediate">中级</option>
          <option value="advanced">高级</option>
        </select>
        <select v-model="profile.goal" class="input-mini">
          <option value="strength">增力</option>
          <option value="hypertrophy">增肌</option>
          <option value="endurance">耐力</option>
          <option value="weight_loss">减脂</option>
          <option value="general">综合</option>
        </select>
      </div>

      <button @click="generatePlan" :disabled="generating"
              class="btn-primary rounded-lg py-2 text-[10px] font-semibold w-full">
        {{ generating ? '生成中...' : '生成周计划' }}
      </button>

      <!-- Plan display -->
      <div v-if="plan" class="flex flex-col gap-1.5">
        <div class="text-[10px] text-gray-400 text-center">
          {{ plan.user_name }} · {{ plan.goal }} · {{ plan.level }}
        </div>
        <div v-for="day in plan.days" :key="day.day"
             class="rounded-lg p-2 bg-white/[0.03] border border-white/[0.06]">
          <div class="flex justify-between items-center mb-1">
            <span class="text-[11px] text-flame font-semibold">{{ day.day }}</span>
            <span class="text-[9px] text-gray-500">{{ day.focus }}</span>
          </div>
          <div v-for="ex in day.exercises" :key="ex.name"
               class="text-[10px] text-gray-300 flex justify-between ml-1">
            <span>{{ ex.name }}</span>
            <span class="text-gray-500">{{ ex.sets }}组×{{ ex.reps }}次 · 休{{ ex.rest_seconds }}s</span>
          </div>
        </div>
      </div>

      <div v-if="error" class="text-[10px] text-danger">{{ error }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import type { WeeklyPlan } from '../types'

const profile = reactive({
  name: '用户',
  age: 25,
  weight_kg: 70,
  height_cm: 170,
  fitness_level: 'beginner',
  goal: 'general',
  equipment: 'mat',
})

const plan = ref<WeeklyPlan | null>(null)
const generating = ref(false)
const error = ref('')

async function generatePlan() {
  generating.value = true
  error.value = ''
  plan.value = null
  try {
    // Save profile first
    await fetch('http://localhost:8000/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    })
    // Generate plan
    const res = await fetch('http://localhost:8000/api/plan/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    })
    const data = await res.json()
    if (data.error) {
      error.value = data.error
    } else {
      plan.value = data as WeeklyPlan
    }
  } catch (e: any) {
    error.value = '连接失败: ' + (e.message || '')
  }
  generating.value = false
}
</script>

<style scoped>
.input-mini {
  @apply bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1.5 text-[10px] text-white outline-none;
}
.input-mini:focus {
  @apply border-flame/40;
}
</style>
