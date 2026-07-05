<template>
  <div class="flat-card p-3.5 flex-1 flex flex-col min-h-0">
    <div class="text-[10px] uppercase tracking-wider text-steel font-semibold mb-2 flex items-center gap-2">
      <span>AI Coach</span>
      <!-- Cue tracking indicator -->
      <span v-if="hasActiveCueTracking"
            class="px-1.5 py-0.5 rounded-full text-[7px] bg-amber-500/15 text-amber-400 border border-amber-500/25 animate-pulse"
            title="教练正在追踪指导效果，如有必要会切换策略">
        🎯 追踪中
      </span>
    </div>
    <div ref="messagesRef" class="flex-1 overflow-y-auto flex flex-col gap-1.5 pb-2">
      <div v-for="(msg, i) in messages" :key="i"
           class="max-w-[92%] rounded-lg px-3 py-2 text-[10px]"
           :class="msg.role === 'ai'
             ? msg.proactive
               ? 'bg-mist border border-concrete border-l-[3px] border-l-flame text-obsidian self-start'
               : 'bg-mist border border-concrete text-obsidian self-start'
             : 'bg-paper border border-concrete text-steel self-end'">
        <!-- Proactive coach badge with trigger type -->
        <div v-if="msg.proactive && msg.triggerMeta" class="flex items-center gap-1.5 mb-1">
          <span class="text-[11px]">{{ msg.triggerMeta.icon }}</span>
          <span class="text-[8px] uppercase tracking-wider font-semibold" :class="msg.triggerMeta.color">
            {{ msg.triggerMeta.label }}
          </span>
        </div>
        <span v-else-if="msg.proactive" class="text-[8px] text-flame/60 uppercase tracking-wider mr-1">⚡ 教练提示</span>

        <!-- Main text -->
        <div class="whitespace-pre-wrap leading-relaxed">{{ msg.text }}</div>

        <!-- Diagnosis details (collapsible) -->
        <div v-if="msg.diagnosis && Object.keys(msg.diagnosis).length > 0 && !msg.diagnosis.raw_diagnosis" class="mt-2 pt-2 border-t border-concrete">
          <button
            class="text-[9px] text-steel hover:text-obsidian transition-colors flex items-center gap-1"
            @click="msg.showDiagnosis = !msg.showDiagnosis"
          >
            <span class="transition-transform duration-200" :class="msg.showDiagnosis ? 'rotate-90' : ''">▸</span>
            {{ msg.showDiagnosis ? '收起诊断详情' : '查看诊断详情' }}
          </button>
          <div v-if="msg.showDiagnosis" class="mt-2 space-y-1.5 text-[9px] animate-[fadeIn_0.2s_ease-out]">
            <!-- Root cause -->
            <div v-if="msg.diagnosis.root_cause" class="flex gap-1.5">
              <span class="text-faint shrink-0 w-12">🔍 根因</span>
              <span class="text-obsidian">{{ msg.diagnosis.root_cause }}</span>
            </div>
            <!-- Confidence bar -->
            <div v-if="msg.diagnosis.confidence != null" class="flex gap-1.5 items-center">
              <span class="text-faint shrink-0 w-12">📊 置信度</span>
              <div class="flex-1 h-1.5 rounded-full bg-concrete overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="msg.diagnosis.confidence >= 0.7 ? 'bg-emerald-500' : msg.diagnosis.confidence >= 0.4 ? 'bg-amber-500' : 'bg-red-500'"
                  :style="{ width: (msg.diagnosis.confidence * 100) + '%' }"
                />
              </div>
              <span class="text-steel w-8 text-right">{{ (msg.diagnosis.confidence * 100).toFixed(0) }}%</span>
            </div>
            <!-- Affected joints -->
            <div v-if="msg.diagnosis.affected_joints?.length" class="flex gap-1.5">
              <span class="text-faint shrink-0 w-12">🦴 涉及关节</span>
              <span class="text-obsidian">{{ msg.diagnosis.affected_joints.join('、') }}</span>
            </div>
            <!-- Expected effect -->
            <div v-if="msg.diagnosis.expected_effect" class="flex gap-1.5">
              <span class="text-faint shrink-0 w-12">🎯 预期效果</span>
              <span class="text-obsidian">{{ msg.diagnosis.expected_effect }}</span>
            </div>
            <!-- Recommended cues -->
            <div v-if="msg.recommendedCues?.length" class="mt-1.5">
              <div class="text-faint mb-1.5 text-[8px] uppercase tracking-wider">📋 推荐指导策略</div>
              <div
                v-for="(cue, ci) in msg.recommendedCues" :key="ci"
                class="flex items-center gap-1.5 py-1 pl-1"
              >
                <span
                  class="px-1.5 py-0.5 rounded text-[7px] font-bold uppercase shrink-0"
                  :class="cue.tier === 1
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : cue.tier === 2
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'"
                >
                  Tier {{ cue.tier }}
                </span>
                <span class="text-obsidian">{{ cue.cue }}</span>
                <span v-if="cue.focus && cue.focus !== 'unknown'" class="text-[7px] text-faint">
                  ({{ cue.focus === 'external' ? '外部注意力' : cue.focus === 'internal' ? '内部注意力' : '回归训练' }})
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Fallback: raw diagnosis text when JSON parsing failed -->
        <div v-if="msg.diagnosis?.raw_diagnosis" class="mt-2 pt-2 border-t border-concrete">
          <div class="text-[8px] text-faint mb-1">诊断原文（解析失败）</div>
          <div class="text-[9px] text-steel whitespace-pre-wrap">{{ msg.diagnosis.raw_diagnosis }}</div>
        </div>
      </div>
    </div>
    <div class="flex gap-1.5 mt-2">
      <input v-model="input" @keyup.enter="send"
             class="flex-1 bg-mist border border-concrete rounded-lg px-3 py-2 text-[10px] text-obsidian outline-none placeholder:text-faint"
             placeholder="问问AI教练..." />
      <button @click="send" class="pill-btn w-8 h-8 text-xs flex items-center justify-center">→</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import type { PoseContext, CoachMessage, CueTrackingData, DiagnosisData, RecommendedCue } from '../types'
import { COACH_TRIGGER_META } from '../types'
import { config } from '../config'

const props = defineProps<{
  poseContext?: PoseContext
  coachMessage?: CoachMessage | null
  cueTracking?: CueTrackingData | null
}>()

const hasActiveCueTracking = computed(() => {
  const ct = props.cueTracking
  return ct && ct.active_cues && ct.active_cues.length > 0
})

interface Message {
  role: 'ai' | 'user'
  text: string
  proactive?: boolean
  triggerMeta?: { label: string; icon: string; color: string }
  diagnosis?: DiagnosisData | null
  recommendedCues?: RecommendedCue[] | null
  showDiagnosis?: boolean
}

const messages = ref<Message[]>([
  { role: 'ai', text: '你好！我是你的AI健身教练，有什么可以帮你的？' }
])
const input = ref('')
const messagesRef = ref<HTMLElement | null>(null)

// Watch for proactive coach pushes from backend WebSocket
watch(() => props.coachMessage, (msg) => {
  if (msg && msg.text) {
    const triggerMeta = COACH_TRIGGER_META[msg.trigger] || COACH_TRIGGER_META.proactive
    messages.value.push({
      role: 'ai',
      text: msg.text,
      proactive: true,
      triggerMeta,
    })
    nextTick(() => scrollToBottom())
  }
})

async function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', text })
  input.value = ''
  await nextTick()
  scrollToBottom()

  // Build request body — include pose_context when available
  const body: Record<string, unknown> = { message: text }
  if (props.poseContext) {
    body.pose_context = JSON.stringify(props.poseContext)
  }

  try {
    const res = await fetch(config.endpoints.chat, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()

    // Extract reply (try multiple fields for backward compat)
    const reply = data.reply || data.response || data.guidance_text || data.error || '暂无回复'

    // Extract diagnosis and cues from the new two-stage output format
    const diagnosis: DiagnosisData | null = data.diagnosis || null
    const recommendedCues: RecommendedCue[] | null = data.recommended_cues || null

    messages.value.push({
      role: 'ai',
      text: reply,
      diagnosis,
      recommendedCues,
      showDiagnosis: false,
    })
  } catch {
    messages.value.push({ role: 'ai', text: '连接失败，请检查后端服务是否启动。' })
  }
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
}
</script>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
