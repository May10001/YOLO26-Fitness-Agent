<template>
  <div class="glow-card rounded-[14px] p-3.5 flex-1 flex flex-col min-h-0">
    <div class="text-[10px] uppercase tracking-wider text-flame/70 font-semibold mb-2">AI Coach</div>
    <div ref="messagesRef" class="flex-1 overflow-y-auto flex flex-col gap-1.5 pb-2">
      <div v-for="(msg, i) in messages" :key="i"
           class="max-w-[92%] rounded-lg px-3 py-2 text-[10px]"
           :class="msg.role === 'ai'
             ? 'bg-flame/[0.08] border border-flame/[0.12] text-gray-200 self-start'
             : 'bg-white/[0.05] border border-white/[0.08] text-gray-400 self-end'">
        {{ msg.text }}
      </div>
    </div>
    <div class="flex gap-1.5 mt-2">
      <input v-model="input" @keyup.enter="send"
             class="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[10px] text-white outline-none"
             placeholder="问问AI教练..." />
      <button @click="send" class="btn-primary w-8 h-8 rounded-lg text-xs flex items-center justify-center">→</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'

interface Message { role: 'ai' | 'user'; text: string }

const messages = ref<Message[]>([
  { role: 'ai', text: '你好！我是你的AI健身教练，有什么可以帮你的？' }
])
const input = ref('')
const messagesRef = ref<HTMLElement | null>(null)

async function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', text })
  input.value = ''
  await nextTick()
  scrollToBottom()

  try {
    const res = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    })
    const data = await res.json()
    messages.value.push({ role: 'ai', text: data.reply })
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
