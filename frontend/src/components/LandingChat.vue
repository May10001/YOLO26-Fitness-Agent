<template>
  <div class="landing-root" :class="{ 'landing-leave': leaving }">
    <!-- Ray background (always visible) -->
    <div class="ray-bg">
      <div class="ray-glow" />
      <div class="ray-rings">
        <div class="ray-ring" style="border-color:#b7d7f6;width:105%;height:105%;margin-top:-11px;z-index:4" />
        <div class="ray-ring" style="border-color:#8fc1f2;width:110%;height:110%;margin-top:-8px;z-index:3" />
        <div class="ray-ring" style="border-color:#64acf6;width:115%;height:115%;margin-top:-4px;z-index:2" />
        <div class="ray-ring" style="border-color:#1172e2;width:120%;height:120%;z-index:1;box-shadow:0 -15px 24.8px rgba(17,114,226,0.6)" />
      </div>
    </div>

    <!-- ===== MODE: Welcome (no chat yet) ===== -->
    <div v-if="!chatStarted" class="landing-welcome">
      <h1 class="landing-title">
        For<span class="landing-title-accent">MAI</span>
      </h1>
      <p class="landing-sub">你的专属 AI 健身教练 · 实时动作诊断与智能纠错</p>

      <div class="chat-wrapper">
        <div class="chat-input-shell">
          <textarea
            ref="inputRef"
            v-model="message"
            @keydown.enter.exact.prevent="send"
            placeholder="描述你的训练需求，AI 将为你制定个性化方案..."
            class="chat-textarea"
            :style="{ height: inputHeight + 'px' }"
          />
          <div class="chat-actions">
            <div class="flex-1" />
            <button @click="send" :disabled="!message.trim()" class="chat-send-btn">
              <span class="hidden sm:inline mr-1.5">发送</span>
              <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
            </button>
          </div>
        </div>
        <div class="quick-prompts">
          <button v-for="p in quickPrompts" :key="p" @click="sendPrompt(p)" class="quick-prompt">{{ p }}</button>
        </div>
      </div>

      <button @click="onEnter" class="enter-btn">
        直接开始训练
        <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
      </button>
    </div>

    <!-- ===== MODE: Active chat ===== -->
    <div v-else class="landing-chat">
      <!-- Chat header -->
      <div class="chat-header">
        <div class="chat-header-brand">
          <span class="chat-header-logo">For<span class="text-blue-400 italic">MAI</span></span>
          <span class="chat-header-badge">AI 教练对话</span>
        </div>
        <div class="chat-header-actions">
          <button @click="chatStarted = false" class="chat-header-btn">新对话</button>
          <button @click="onEnter" class="enter-btn-sm">开始训练</button>
        </div>
      </div>

      <!-- Messages -->
      <div ref="msgList" class="chat-messages">
        <div v-for="(msg, i) in chatMessages" :key="i"
             class="chat-msg"
             :class="msg.role === 'user' ? 'chat-msg-user' : 'chat-msg-ai'">
          <div class="chat-msg-avatar">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
          <div class="chat-msg-bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-ai'">
            <div class="whitespace-pre-wrap text-[13px] leading-relaxed">{{ msg.text }}</div>
          </div>
        </div>
        <!-- Generating dots -->
        <div v-if="streaming && !streamText" class="chat-msg chat-msg-ai">
          <div class="chat-msg-avatar">AI</div>
          <div class="chat-msg-bubble bubble-ai">
            <span class="gen-dot" />
            <span class="gen-dot" style="animation-delay:0.15s" />
            <span class="gen-dot" style="animation-delay:0.3s" />
          </div>
        </div>
      </div>

      <!-- Chat input (bottom) -->
      <div class="chat-input-bar">
        <div class="chat-input-shell chat-input-sm">
          <input
            v-model="message"
            @keydown.enter="send"
            placeholder="输入消息..."
            class="chat-input-line"
          />
          <button @click="send" :disabled="!message.trim() || loading" class="chat-send-mini">
            <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { config } from '../config'

const emit = defineEmits<{ (e: 'enter'): void }>()

const message = ref('')
const leaving = ref(false)
const chatStarted = ref(false)
const loading = ref(false)
const streaming = ref(false)
const streamText = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const msgList = ref<HTMLElement | null>(null)
const inputHeight = ref(80)

const quickPrompts = [
  '今天练腿部，30 分钟中等强度',
  '我是新手，帮我制定入门训练计划',
  '想改善深蹲姿势，膝盖容易内扣',
  '推荐一套燃脂训练，15 分钟',
]

interface ChatMsg { role: 'user' | 'ai'; text: string }
const chatMessages = ref<ChatMsg[]>([])

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  inputHeight.value = Math.min(el.scrollHeight, 160)
}

function sendPrompt(p: string) { message.value = p; send() }

async function send() {
  const text = message.value.trim()
  if (!text || loading.value) return
  message.value = ''
  if (!chatStarted.value) chatStarted.value = true

  chatMessages.value.push({ role: 'user', text })
  loading.value = true
  streaming.value = true
  streamText.value = ''

  const aiIdx = chatMessages.value.length
  chatMessages.value.push({ role: 'ai', text: '' })

  await nextTick(); scrollDown()

  try {
    const res = await fetch(config.endpoints.chat, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, stream: true }),
    })
    const ct = res.headers.get('content-type') || ''
    if (ct.includes('text/event-stream')) {
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const d = JSON.parse(line.slice(6))
            if (d.done) {
              chatMessages.value[aiIdx].text = streamText.value
              streamText.value = ''; streaming.value = false
            } else if (d.text) {
              streamText.value += d.text
              chatMessages.value[aiIdx].text = streamText.value
            }
          } catch { /* skip */ }
        }
      }
    } else {
      const data = await res.json()
      chatMessages.value[aiIdx].text = data.reply || data.response || '暂无回复'
      streamText.value = ''; streaming.value = false
    }
  } catch {
    chatMessages.value[aiIdx].text = streamText.value || '连接失败，请检查后端。'
    streamText.value = ''; streaming.value = false
  }
  loading.value = false
  await nextTick(); scrollDown()
}

function scrollDown() {
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
}

function onEnter() {
  leaving.value = true
  setTimeout(() => emit('enter'), 500)
}

onMounted(() => nextTick(autoResize))
</script>

<style scoped>
.landing-root {
  position: fixed; inset: 0; z-index: 40;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: #0f0f10; overflow: hidden;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
  transition: opacity .5s ease, transform .5s ease;
}
.landing-leave { opacity: 0; transform: scale(1.03); }

/* ---- Ray background ---- */
.ray-bg { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
.ray-glow {
  position: absolute; left: 50%; transform: translateX(-50%);
  width: 4000px; height: 1800px;
  background: radial-gradient(circle at center 800px, rgba(20,136,252,0.7) 0%, rgba(20,136,252,0.25) 12%, rgba(20,136,252,0.12) 18%, rgba(20,136,252,0.04) 22%, rgba(15,15,16,0.2) 25%);
}
.ray-rings {
  position: absolute; bottom: -800px; left: 50%; transform: translateX(-50%) rotate(180deg);
  width: 1600px; height: 1600px;
}
.ray-ring {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  border-radius: 50%; border: 23px solid transparent;
}

/* ===== Welcome mode ===== */
.landing-welcome {
  position: relative; z-index: 10;
  display: flex; flex-direction: column; align-items: center;
  width: 100%; max-width: 720px; padding: 0 24px;
}
.landing-title {
  font-size: clamp(3rem, 8vw, 5.5rem); font-weight: 800;
  color: #fff; letter-spacing: -0.02em; margin: 0; line-height: 1.1;
  text-shadow: 0 0 80px rgba(20,136,252,0.3); padding: 0 0.05em 0.1em 0;
}
.landing-title-accent {
  background: linear-gradient(180deg, #4da5fc, #fff);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; font-style: italic;
}
.landing-sub {
  margin-top: 12px; font-size: 14px; color: #8a8a8f; font-weight: 500;
}
.chat-wrapper { width: 100%; margin: 32px 0 28px; }
.chat-input-shell {
  position: relative; width: 100%; border-radius: 16px; background: #1e1e22;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.05), 0 2px 20px rgba(0,0,0,0.4);
  overflow: hidden;
}
.chat-input-shell::before {
  content: ''; position: absolute; inset: -1px; border-radius: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0.08), transparent);
  pointer-events: none; z-index: 1;
}
.chat-textarea {
  width: 100%; resize: none; background: transparent;
  border: none; outline: none; color: #fff; font-size: 15px; line-height: 1.6;
  padding: 20px 20px 12px; min-height: 80px; max-height: 160px;
  font-family: 'Inter', sans-serif;
}
.chat-textarea::placeholder { color: #5a5a5f; }
.chat-actions {
  display: flex; align-items: center; gap: 8px; padding: 6px 12px 12px;
}
.chat-send-btn {
  display: flex; align-items: center; gap: 4px; padding: 8px 18px;
  border-radius: 24px; background: #1488fc; color: #fff;
  font-size: 14px; font-weight: 600; border: none; cursor: pointer;
  transition: all .2s ease; box-shadow: 0 0 20px rgba(20,136,252,0.3);
  font-family: 'Inter', sans-serif;
}
.chat-send-btn:hover { background: #1a94ff; transform: scale(1.02); }
.chat-send-btn:active { transform: scale(0.95); }
.chat-send-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
.quick-prompts { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.quick-prompt {
  padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04); color: #8a8a8f;
  font-size: 12px; cursor: pointer; transition: all .2s ease;
  font-family: 'Inter', sans-serif;
}
.quick-prompt:hover { border-color: rgba(20,136,252,0.4); color: #fff; background: rgba(20,136,252,0.08); }
.enter-btn {
  display: flex; align-items: center; gap: 8px; padding: 14px 36px;
  border-radius: 30px; border: none;
  background: linear-gradient(135deg, #1488fc, #0d6dd4);
  color: #fff; font-size: 16px; font-weight: 700;
  cursor: pointer; transition: all .3s ease;
  box-shadow: 0 4px 24px rgba(20,136,252,0.3);
  font-family: 'Inter', sans-serif;
}
.enter-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(20,136,252,0.45); }
.enter-btn:active { transform: translateY(0); }

/* ===== Chat mode ===== */
.landing-chat {
  position: relative; z-index: 10;
  display: flex; flex-direction: column;
  width: 100%; max-width: 760px; height: 100vh; padding: 0 16px;
}
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 8px; flex-shrink: 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.chat-header-brand { display: flex; align-items: center; gap: 8px; }
.chat-header-logo { font-size: 18px; font-weight: 800; color: #fff; }
.chat-header-badge {
  font-size: 10px; color: #1488fc; background: rgba(20,136,252,0.12);
  padding: 2px 8px; border-radius: 10px; font-weight: 600;
}
.chat-header-actions { display: flex; align-items: center; gap: 8px; }
.chat-header-btn {
  font-size: 12px; color: #8a8a8f; background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
  padding: 5px 14px; cursor: pointer; transition: all .2s ease;
  font-family: 'Inter', sans-serif;
}
.chat-header-btn:hover { color: #fff; border-color: rgba(255,255,255,0.2); }
.enter-btn-sm {
  font-size: 12px; font-weight: 600; color: #fff;
  background: #1488fc; border: none; border-radius: 16px;
  padding: 5px 14px; cursor: pointer; transition: all .2s ease;
  font-family: 'Inter', sans-serif;
}
.enter-btn-sm:hover { background: #1a94ff; }

.chat-messages {
  flex: 1; overflow-y: auto; padding: 16px 4px;
  display: flex; flex-direction: column; gap: 16px;
}
.chat-msg { display: flex; gap: 10px; max-width: 92%; }
.chat-msg-user { align-self: flex-end; flex-direction: row-reverse; }
.chat-msg-ai { align-self: flex-start; }
.chat-msg-bubble { border-radius: 16px; padding: 10px 14px; }
.bubble-user { background: #1488fc; color: #fff; border-bottom-right-radius: 4px; }
.bubble-ai { background: #1e1e22; color: #e0e0e0; border: 1px solid rgba(255,255,255,0.06); border-bottom-left-radius: 4px; }
.chat-msg-avatar {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700; flex-shrink: 0;
}
.chat-msg-user .chat-msg-avatar { background: #0d6dd4; color: #fff; }
.chat-msg-ai .chat-msg-avatar { background: #2a2a30; color: #8a8a8f; }

.chat-input-bar { padding: 10px 4px 16px; flex-shrink: 0; }
.chat-input-sm { display: flex; align-items: center; gap: 8px; padding: 4px; }
.chat-input-line {
  flex: 1; background: transparent; border: none; outline: none;
  color: #fff; font-size: 14px; padding: 8px 4px 8px 12px;
  font-family: 'Inter', sans-serif;
}
.chat-input-line::placeholder { color: #5a5a5f; }
.chat-send-mini {
  width: 36px; height: 36px; border-radius: 50%;
  background: #1488fc; color: #fff; border: none;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all .2s ease; flex-shrink: 0;
}
.chat-send-mini:hover { background: #1a94ff; }
.chat-send-mini:disabled { opacity: 0.4; cursor: not-allowed; }

/* ---- Generating dots ---- */
.gen-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: #8a8a8f; margin: 0 2px;
  animation: gen-float 0.9s ease-in-out infinite;
}
@keyframes gen-float {
  0%, 100% { opacity: 0.3; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-4px); }
}
</style>
