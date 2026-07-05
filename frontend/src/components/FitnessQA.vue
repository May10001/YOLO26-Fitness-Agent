<template>
  <div class="flat-card p-4 flex flex-col max-h-[calc(100vh-200px)]">
    <div class="text-[10px] uppercase tracking-wider text-steel font-semibold mb-3">Fitness Q&A</div>

    <!-- Messages -->
    <div ref="msgList" class="flex-1 overflow-y-auto space-y-3 mb-3 pr-1">
      <div v-if="messages.length === 0"
           class="text-[11px] text-faint text-center py-8">
        基于 1600+ 条健身专业知识库<br/>可以问我动作纠正、训练计划、伤病预防等问题
      </div>
      <div v-for="(msg, i) in messages" :key="i"
           class="rounded-xl p-3 text-[11px] leading-relaxed"
           :class="msg.role === 'user'
             ? 'bg-paper border border-concrete ml-8'
             : 'bg-mist border border-concrete mr-4'">
        <div class="text-[9px] text-faint mb-1">{{ msg.role === 'user' ? '你' : 'ForMAI' }}</div>
        <div class="text-obsidian whitespace-pre-wrap">{{ msg.content }}</div>
        <!-- Sources -->
        <div v-if="msg.sources && msg.sources.length" class="mt-2 pt-2 border-t border-concrete">
          <div class="text-[8px] text-faint mb-1">参考来源</div>
          <div v-for="(s, si) in msg.sources" :key="si"
               class="text-[9px] text-steel flex gap-1.5 items-start mb-0.5">
            <span class="px-1 py-0.5 rounded text-[8px] shrink-0 bg-concrete text-steel">{{ s.source }}</span>
            <span class="truncate">{{ s.snippet }}</span>
          </div>
        </div>
      </div>
      <!-- Loading indicator -->
      <div v-if="loading" class="flex items-center gap-2 text-[10px] text-steel px-3">
        <span class="w-1.5 h-1.5 rounded-full bg-obsidian animate-pulse" />
        <span class="w-1.5 h-1.5 rounded-full bg-obsidian animate-pulse" style="animation-delay: 0.15s" />
        <span class="w-1.5 h-1.5 rounded-full bg-obsidian animate-pulse" style="animation-delay: 0.3s" />
        检索知识库中...
      </div>
    </div>

    <!-- Input -->
    <div class="flex gap-2">
      <input v-model="question" @keydown.enter="ask"
             placeholder="问一个健身问题..."
             class="flex-1 bg-mist border border-concrete rounded-lg px-3 py-2 text-[11px] text-obsidian outline-none focus:border-steel transition-colors placeholder:text-faint" />
      <button @click="ask" :disabled="loading || !question.trim()"
              class="pill-btn px-4 py-2 text-[11px] font-bold disabled:opacity-30 transition-opacity">
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
      body: JSON.stringify({ question: q }),
    })
    const data = await res.json()
    messages.value.push({
      role: 'assistant',
      content: data.answer || '抱歉，暂时无法回答。',
      sources: data.sources || [],
    })
  } catch {
    messages.value.push({ role: 'assistant', content: '网络错误，请重试。' })
  } finally {
    loading.value = false
    await nextTick()
    scrollDown()
  }
}

function scrollDown() {
  if (msgList.value) {
    msgList.value.scrollTop = msgList.value.scrollHeight
  }
}
</script>
