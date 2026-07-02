<template>
  <div class="glow-card rounded-[14px] p-4 space-y-4 max-h-[calc(100vh-200px)] overflow-y-auto">
    <div class="text-[10px] uppercase tracking-wider text-flame/80 font-semibold">Profile</div>

    <!-- Basic Info -->
    <div class="grid grid-cols-2 gap-2.5">
      <div>
        <label class="text-[9px] text-gray-500 block mb-1">姓名</label>
        <input v-model="form.name" class="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-flame/40 transition-colors" />
      </div>
      <div>
        <label class="text-[9px] text-gray-500 block mb-1">年龄</label>
        <input v-model.number="form.age" type="number" min="10" max="99" class="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-flame/40 transition-colors" />
      </div>
      <div>
        <label class="text-[9px] text-gray-500 block mb-1">身高 (cm)</label>
        <input v-model.number="form.height_cm" type="number" min="100" max="250" class="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-flame/40 transition-colors" />
      </div>
      <div>
        <label class="text-[9px] text-gray-500 block mb-1">体重 (kg)</label>
        <input v-model.number="form.weight_kg" type="number" min="30" max="200" class="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-flame/40 transition-colors" />
      </div>
    </div>

    <!-- Goal selector -->
    <div>
      <label class="text-[9px] text-gray-500 block mb-1.5">健身目标</label>
      <div class="grid grid-cols-3 gap-1.5">
        <button v-for="g in goals" :key="g.value"
                class="px-2 py-2 rounded-lg text-[10px] border transition-all"
                :class="form.goal === g.value
                  ? 'bg-flame/20 border-flame/40 text-flame font-semibold'
                  : 'border-white/[0.07] text-gray-500 hover:text-gray-300'"
                @click="form.goal = g.value">
          {{ g.emoji }} {{ g.label }}
        </button>
      </div>
    </div>

    <!-- Level selector -->
    <div>
      <label class="text-[9px] text-gray-500 block mb-1.5">训练水平</label>
      <div class="grid grid-cols-3 gap-1.5">
        <button v-for="l in levels" :key="l.value"
                class="px-2 py-2 rounded-lg text-[10px] border transition-all"
                :class="form.fitness_level === l.value
                  ? 'bg-flame/20 border-flame/40 text-flame font-semibold'
                  : 'border-white/[0.07] text-gray-500 hover:text-gray-300'"
                @click="form.fitness_level = l.value">
          {{ l.label }}
        </button>
      </div>
    </div>

    <!-- Training days -->
    <div>
      <label class="text-[9px] text-gray-500 block mb-1.5">
        每周训练天数: <span class="text-flame font-bold">{{ form.training_days_per_week }}</span>
      </label>
      <input v-model.number="form.training_days_per_week" type="range" min="1" max="6"
             class="w-full h-1.5 rounded-full appearance-none bg-white/[0.08] accent-flame outline-none" />
      <div class="flex justify-between text-[8px] text-gray-600 mt-0.5">
        <span>1天</span><span>2天</span><span>3天</span><span>4天</span><span>5天</span><span>6天</span>
      </div>
    </div>

    <!-- Injury history -->
    <div>
      <label class="text-[9px] text-gray-500 block mb-1">伤病史（可选）</label>
      <textarea v-model="form.injury_history" rows="2"
                placeholder="例如：左膝半月板损伤，避免深度屈膝动作"
                class="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-flame/40 transition-colors resize-none placeholder:text-gray-600" />
    </div>

    <!-- Exercise preferences -->
    <div>
      <label class="text-[9px] text-gray-500 block mb-1.5">动作偏好</label>
      <div class="flex flex-wrap gap-1.5">
        <button v-for="ex in exerciseList" :key="ex"
                class="px-2 py-1 rounded-md text-[9px] border transition-all"
                :class="prefClass(ex)"
                @click="togglePref(ex)">
          {{ ex }}
        </button>
      </div>
      <div class="flex gap-4 mt-2 text-[8px] text-gray-600">
        <span><span class="inline-block w-2 h-2 rounded-full bg-emerald-500/30 mr-1" /> 喜欢</span>
        <span><span class="inline-block w-2 h-2 rounded-full bg-red-500/30 mr-1" /> 不想做</span>
        <span>默认 无偏好</span>
      </div>
    </div>

    <!-- Save -->
    <button @click="saveProfile" :disabled="saving"
            class="w-full py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-flame to-rose text-white shadow-[0_0_20px_rgba(255,106,0,0.2)] hover:shadow-[0_0_30px_rgba(255,106,0,0.4)] transition-all duration-300 disabled:opacity-40">
      {{ saving ? '保存中...' : '保存画像' }}
    </button>
    <div v-if="saveMsg" class="text-[10px] text-center" :class="saveOk ? 'text-emerald-400' : 'text-red-400'">
      {{ saveMsg }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { config } from '../config'

const goals = [
  { value: 'strength', label: '增肌', emoji: '💪' },
  { value: 'weight_loss', label: '减脂', emoji: '🔥' },
  { value: 'general', label: '塑形', emoji: '✨' },
]
const levels = [
  { value: 'beginner', label: '新手' },
  { value: 'intermediate', label: '中级' },
  { value: 'advanced', label: '高级' },
]

const EXERCISE_LIST = ['深蹲', '俯卧撑', '平板支撑', '卷腹', '开合跳', '引体向上', '臀桥', '高抬腿', '肩推', '侧平举']
const exerciseList = ref(EXERCISE_LIST)

const form = reactive({
  name: '用户',
  age: 25,
  weight_kg: 70,
  height_cm: 170,
  goal: 'general',
  fitness_level: 'beginner',
  equipment: 'mat',
  training_days_per_week: 3,
  injury_history: '',
  liked_exercises: [] as string[],
  disliked_exercises: [] as string[],
})

const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)

function prefClass(ex: string) {
  if (form.liked_exercises.includes(ex)) return 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
  if (form.disliked_exercises.includes(ex)) return 'bg-red-500/15 border-red-500/30 text-red-400'
  return 'border-white/[0.07] text-gray-600 hover:text-gray-400'
}

function togglePref(ex: string) {
  const li = form.liked_exercises.indexOf(ex)
  const di = form.disliked_exercises.indexOf(ex)
  if (li >= 0) {
    form.liked_exercises.splice(li, 1)
    form.disliked_exercises.push(ex)
  } else if (di >= 0) {
    form.disliked_exercises.splice(di, 1)
  } else {
    form.liked_exercises.push(ex)
  }
}

async function saveProfile() {
  saving.value = true
  saveMsg.value = ''
  try {
    const body = { ...form, equipment: 'mat' }
    const res = await fetch(config.endpoints.profile, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (res.ok) {
      saveOk.value = true
      saveMsg.value = '画像已保存'
    } else {
      saveOk.value = false
      saveMsg.value = '保存失败'
    }
  } catch {
    saveOk.value = false
    saveMsg.value = '网络错误'
  } finally {
    saving.value = false
  }
}

async function loadProfile() {
  try {
    const res = await fetch(config.endpoints.profileLoad(form.name))
    if (!res.ok) return
    const data = await res.json()
    if (data.name) {
      form.name = data.name || form.name
      form.age = data.age || form.age
      form.weight_kg = data.weight_kg || form.weight_kg
      form.height_cm = data.height_cm || form.height_cm
      form.goal = data.goal || form.goal
      form.fitness_level = data.fitness_level || form.fitness_level
      form.training_days_per_week = data.training_days_per_week || 3
      form.injury_history = data.injury_history || ''
      form.liked_exercises = data.liked_exercises || []
      form.disliked_exercises = data.disliked_exercises || []
    }
  } catch { /* use defaults */ }
}

onMounted(loadProfile)

defineExpose({ form })
</script>
