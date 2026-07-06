<template>
  <div class="flex flex-col h-full max-h-[65vh]">
    <!-- Messages -->
    <div ref="msgList" class="flex-1 overflow-y-auto space-y-3 mb-3 pr-1">
      <div v-if="messages.length === 0"
           class="text-[11px] text-muted text-center py-8">
        基于 1600+ 条健身专业知识库<br/>问动作纠正、训练计划、伤病预防等问题
      </div>
      <div v-for="(msg, i) in messages" :key="i"
           class="rounded-xl p-3 text-[11px] leading-relaxed"
           :class="msg.role === 'user'
             ? 'bg-accent/10 border border-accent/20 ml-6'
             : 'bg-mist border border-concrete mr-4'">
        <div class="text-[9px] text-muted mb-1">{{ msg.role === 'user' ? '你' : 'ForMAI' }}</div>
        <div class="text-obsidian whitespace-pre-wrap">{{ msg.content }}</div>
      </div>
      <!-- Streaming message -->
      <div v-if="streaming" class="rounded-xl p-3 text-[11px] leading-relaxed bg-mist border border-concrete mr-4">
        <div class="text-[9px] text-muted mb-1">ForMAI</div>
        <div class="text-obsidian whitespace-pre-wrap">{{ streamText }}<span class="generating-cursor">|</span></div>
      </div>
      <!-- Generating placeholder -->
      <div v-if="loading && !streaming" class="flex items-center gap-2 text-[10px] text-accent px-3 py-2">
        <span class="generating-dot" />
        <span class="generating-dot" style="animation-delay: 0.15s" />
        <span class="generating-dot" style="animation-delay: 0.3s" />
        <span class="generating-text">generating...</span>
      </div>
    </div>

    <!-- Input -->
    <div class="flex gap-2">
      <input v-model="question" @keydown.enter="ask"
             placeholder="问一个健身问题..."
             class="flex-1 bg-mist border border-concrete rounded-lg px-3 py-2 text-[11px] text-obsidian outline-none focus:border-accent transition-colors placeholder:text-faint" />
      <button @click="ask" :disabled="loading || !question.trim()"
              class="pill-btn px-4 py-2 text-[11px]">
        提问
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { config } from '../config'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: { source: string; snippet: string }[]
}

const props = defineProps<{ initialMessages?: Message[] }>()
const emit = defineEmits<{ (e: 'updateHistory', msgs: Message[]): void }>()

const messages = ref<Message[]>(props.initialMessages || [])
const question = ref('')
const loading = ref(false)
const streaming = ref(false)
const streamText = ref('')
const msgList = ref<HTMLElement | null>(null)

watch(messages, (msgs) => emit('updateHistory', [...msgs]), { deep: true })

async function ask() {
  const q = question.value.trim()
  if (!q || loading.value) return
  question.value = ''
  messages.value.push({ role: 'user', content: q })
  loading.value = true
  await nextTick()
  scrollDown()

  try {
    const res = await fetch(config.endpoints.ragQuery, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, stream: true }),
    })

    if (!res.ok || !res.body) {
      // Fallback to non-streaming
      const data = await res.json()
      messages.value.push({ role: 'assistant', content: data.answer || '抱歉，暂时无法回答。', sources: data.sources })
      loading.value = false
      return
    }

    // Stream reading
    streaming.value = true
    streamText.value = ''
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.done) {
            messages.value.push({ role: 'assistant', content: streamText.value })
            streamText.value = ''
            streaming.value = false
          } else if (data.text) {
            streamText.value += data.text
          }
        } catch { /* skip malformed */ }
      }
    }
  } catch {
    if (streaming.value) {
      messages.value.push({ role: 'assistant', content: streamText.value || '网络错误，请重试。' })
      streamText.value = ''
      streaming.value = false
    } else {
      messages.value.push({ role: 'assistant', content: '网络错误，请重试。' })
    }
  } finally {
    loading.value = false
    await nextTick()
    scrollDown()
  }
}

function scrollDown() {
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
}
</script>

<style scoped>
.generating-cursor {
  animation: blink 0.8s step-end infinite;
  color: var(--accent, #38D6B2);
}
@keyframes blink {
  50% { opacity: 0; }
}
.generating-dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--accent, #38D6B2);
  animation: float-dot 0.9s ease-in-out infinite;
}
@keyframes float-dot {
  0%, 100% { opacity: 0.3; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-4px); }
}
.generating-text {
  animation: float-text 1.2s ease-in-out infinite;
}
@keyframes float-text {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}
</style>
