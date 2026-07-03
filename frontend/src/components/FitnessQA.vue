<template>
  <div class="glow-card rounded-[14px] p-4 flex flex-col max-h-[calc(100vh-200px)]">
    <div class="text-[10px] uppercase tracking-wider text-flame/80 font-semibold mb-3">Fitness Q&A</div>

    <!-- Messages -->
    <div ref="msgList" class="flex-1 overflow-y-auto space-y-3 mb-3 pr-1">
      <div v-if="messages.length === 0"
           class="text-[11px] text-gray-600 text-center py-8">
        基于 1600+ 条健身专业知识库<br/>可以问我动作纠正、训练计划、伤病预防等问题
      </div>
      <div v-for="(msg, i) in messages" :key="i"
           class="rounded-xl p-3 text-[11px] leading-relaxed"
           :class="msg.role === 'user'
             ? 'bg-flame/10 border border-flame/20 ml-8'
             : 'bg-white/[0.03] border border-white/[0.06] mr-4'">
        <div class="text-[9px] text-gray-600 mb-1">{{ msg.role === 'user' ? '你' : 'ForMAI' }}</div>
        <div class="text-gray-200 whitespace-pre-wrap">{{ msg.content }}</div>
        <!-- Sources -->
        <div v-if="msg.sources && msg.sources.length" class="mt-2 pt-2 border-t border-white/[0.06]">
          <div class="text-[8px] text-gray-600 mb-1">参考来源</div>
          <div v-for="(s, si) in msg.sources" :key="si"
               class="text-[9px] text-gray-500 flex gap-1.5 items-start mb-0.5">
            <span class="px-1 py-0.5 rounded text-[8px] shrink-0 bg-flame/10 text-flame/80">{{ s.source }}</span>
            <span class="truncate">{{ s.snippet }}</span>
          </div>
        </div>
      </div>
      <!-- Loading indicator -->
      <div v-if="loading" class="flex items-center gap-2 text-[10px] text-gray-500 px-3">
        <span class="w-1.5 h-1.5 rounded-full bg-flame animate-pulse" />
        <span class="w-1.5 h-1.5 rounded-full bg-flame animate-pulse" style="animation-delay: 0.15s" />
        <span class="w-1.5 h-1.5 rounded-full bg-flame animate-pulse" style="animation-delay: 0.3s" />
        检索知识库中...
      </div>
    </div>

    <!-- Input -->
    <div class="flex gap-2">
      <input v-model="question" @keydown.enter="ask"
             placeholder="问一个健身问题..."
             class="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[11px] text-white outline-none focus:border-flame/40 transition-colors placeholder:text-gray-600" />
      <button @click="ask" :disabled="loading || !question.trim()"
              class="px-4 py-2 rounded-lg text-[11px] font-bold bg-gradient-to-r from-flame to-rose text-white disabled:opacity-30 transition-opacity">
        提问
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { config } from '../config'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: { source: string; snippet: string }[]
}

const messages = ref<Message[]>([])
const question = ref('')
const loading = ref(false)
const msgList = ref<HTMLElement | null>(null)

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
