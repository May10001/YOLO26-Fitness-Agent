<template>
  <div class="landing-root" :class="{ 'landing-leave': leaving }">
    <!-- ===== MODE: Welcome ===== -->
    <template v-if="!chatStarted">
      <!-- Nav header -->
      <header class="landing-nav">
        <div class="landing-nav-brand">
          <img src="/assets/logo.png" alt="ForMAI" class="landing-nav-logo" />
          <span class="landing-nav-mark font-display">ForMAI</span>
        </div>
        <button class="nav-liquid-btn" type="button" @click="onEnter">
          <span class="nav-liquid-btn-inner">开始训练 <span class="arrow">↗</span></span>
        </button>
      </header>

      <!-- Main -->
      <main class="landing-main">
        <div class="hero-eyebrow reveal">AI-POWERED FITNESS COACH</div>
        <h1 class="hero-title font-display reveal">
          <span class="hero-line"><span class="hero-line-inner">你的专属</span></span>
          <span class="hero-line"><span class="hero-line-inner">AI 健身教练</span></span>
        </h1>
        <p class="hero-sub reveal">
          描述你的训练需求，AI 为你定制个性化健身方案。
        </p>

        <!-- Chat input -->
        <div class="chat-wrapper reveal">
          <div class="chat-input-shell">
            <textarea
              ref="inputRef"
              v-model="message"
              @keydown.enter.exact.prevent="send"
              placeholder="例如：今天练腿部，30 分钟中等强度..."
              class="chat-textarea"
              :style="{ height: inputHeight + 'px' }"
            />
            <div class="chat-actions">
              <div class="flex-1" />
              <button @click="send" :disabled="!message.trim()" class="chat-send-btn">
                发送
                <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
              </button>
            </div>
          </div>
          <div class="quick-prompts">
            <button v-for="p in quickPrompts" :key="p" @click="sendPrompt(p)" class="quick-prompt">{{ p }}</button>
          </div>
        </div>

        <div class="hero-scroll reveal">
          <span>或直接开始训练</span>
        </div>
      </main>
    </template>

    <!-- ===== MODE: Chat ===== -->
    <template v-else>
      <header class="chat-header-bar">
        <div class="flex items-center gap-2.5">
          <img src="/assets/logo.png" alt="ForMAI" class="w-7 h-7" />
          <span class="font-display font-semibold text-base text-white tracking-wide">ForMAI</span>
          <span class="text-[10px] text-white/40 bg-white/5 px-2 py-0.5 rounded-full">AI 教练</span>
        </div>
        <div class="flex items-center gap-3">
          <button @click="chatStarted = false; chatMessages = []" class="text-xs text-white/50 hover:text-white/80 transition-colors">新对话</button>
          <button @click="onEnter" class="header-cta-btn">开始训练 <span class="arrow">↗</span></button>
        </div>
      </header>

      <div ref="msgList" class="chat-msg-area">
        <div v-for="(msg, i) in chatMessages" :key="i"
             class="chat-msg-row" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
          <div class="chat-msg-bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-ai'">
            <div class="text-[13px] leading-relaxed whitespace-pre-wrap">{{ msg.text }}</div>
          </div>
        </div>
        <div v-if="streaming && !streamText" class="chat-msg-row justify-start">
          <div class="bubble-ai chat-msg-bubble">
            <span class="gen-dot" /><span class="gen-dot" style="animation-delay:0.15s" /><span class="gen-dot" style="animation-delay:0.3s" />
          </div>
        </div>
      </div>

      <div class="chat-input-bar">
        <div class="chat-input-row">
          <input v-model="message" @keydown.enter="send" placeholder="输入消息..."
                 class="flex-1 bg-transparent outline-none text-white/90 text-sm px-4" />
          <button @click="send" :disabled="!message.trim() || loading" class="chat-send-icon">
            <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
          </button>
        </div>
      </div>
    </template>

    <!-- SVG filter for liquid glass -->
    <svg class="hidden">
      <defs>
        <filter id="liquid-glass" x="0%" y="0%" width="100%" height="100%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.04 0.04" numOctaves="1" seed="1" result="turbulence" />
          <feGaussianBlur in="turbulence" stdDeviation="2" result="blurredNoise" />
          <feDisplacementMap in="SourceGraphic" in2="blurredNoise" scale="40" xChannelSelector="R" yChannelSelector="B" result="displaced" />
          <feGaussianBlur in="displaced" stdDeviation="3" result="finalBlur" />
          <feComposite in="finalBlur" in2="finalBlur" operator="over" />
        </filter>
      </defs>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
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
  '我是新手，帮我制定入门计划',
  '改善深蹲姿势，膝盖容易内扣',
  '推荐一套 15 分钟燃脂训练',
]

interface ChatMsg { role: 'user' | 'ai'; text: string }
const chatMessages = ref<ChatMsg[]>([])

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  inputHeight.value = Math.min(el.scrollHeight, 140)
}

function sendPrompt(p: string) { message.value = p; send() }

async function send() {
  const text = message.value.trim()
  if (!text || loading.value) return
  message.value = ''
  if (!chatStarted.value) chatStarted.value = true

  chatMessages.value.push({ role: 'user', text })
  loading.value = true; streaming.value = true; streamText.value = ''
  const aiIdx = chatMessages.value.length
  chatMessages.value.push({ role: 'ai', text: '' })
  await nextTick(); scrollDown()

  try {
    const res = await fetch(config.endpoints.chat, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, stream: true }),
    })
    const ct = res.headers.get('content-type') || ''
    if (ct.includes('text/event-stream')) {
      const reader = res.body!.getReader()
      const decoder = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const d = JSON.parse(line.slice(6))
            if (d.done) { chatMessages.value[aiIdx].text = streamText.value; streamText.value = ''; streaming.value = false }
            else if (d.text) { streamText.value += d.text; chatMessages.value[aiIdx].text = streamText.value }
          } catch { /* skip */ }
        }
      }
    } else {
      const data = await res.json()
      chatMessages.value[aiIdx].text = data.reply || data.response || '暂无回复'
      streamText.value = ''; streaming.value = false
    }
  } catch {
    chatMessages.value[aiIdx].text = streamText.value || '连接失败'
    streamText.value = ''; streaming.value = false
  }
  loading.value = false; await nextTick(); scrollDown()
}

function scrollDown() { if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight }
function onEnter() { leaving.value = true; setTimeout(() => emit('enter'), 500) }
onMounted(() => nextTick(autoResize))
</script>

<style scoped>
.landing-root {
  position: fixed; inset: 0; z-index: 40;
  background: #05080C; color: #fff;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
  transition: opacity .5s ease, transform .5s ease;
  overflow: hidden;
}
.landing-leave { opacity: 0; transform: scale(1.03); }

/* ===== Nav / Header ===== */
.landing-nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px clamp(24px, 5vw, 60px);
}
.landing-nav-brand { display: flex; align-items: center; gap: 12px; }
.landing-nav-logo { height: clamp(36px, 4vw, 52px); width: auto; }
.landing-nav-mark {
  font-weight: 600; font-size: clamp(20px, 2.2vw, 26px);
  letter-spacing: .02em; text-transform: uppercase; color: #fff;
}

/* Liquid glass nav button */
.nav-liquid-btn {
  cursor: pointer; position: relative; display: inline-flex; align-items: center; gap: .4em;
  border: none; border-radius: 28px; padding: 2px;
  background: linear-gradient(180deg, rgba(255,255,255,0.3), rgba(255,255,255,0.06));
  box-shadow: 0 2px 12px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.4);
  font-family: 'Inter', sans-serif; font-weight: 500; font-size: 14px;
  transition: all .3s cubic-bezier(.16,1,.3,1);
}
.nav-liquid-btn:hover { transform: scale(1.05); box-shadow: 0 4px 20px rgba(0,0,0,0.14), inset 0 1px 0 rgba(255,255,255,0.55); }
.nav-liquid-btn:active { transform: scale(0.96); }
.nav-liquid-btn-inner {
  display: inline-flex; align-items: center; gap: .4em;
  background: linear-gradient(180deg, rgba(255,255,255,0.5), rgba(255,255,255,0.2));
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  color: #fff; border-radius: 26px; padding: 8px 20px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}
.nav-liquid-btn .arrow { transition: transform .3s cubic-bezier(.16,1,.3,1); }
.nav-liquid-btn:hover .arrow { transform: translate(2px,-2px); }

/* ===== Welcome Main ===== */
.landing-main {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 0 24px 40px; text-align: center;
}
.hero-eyebrow {
  font-size: clamp(11px, 1vw, 13px); font-weight: 500; letter-spacing: .28em;
  text-transform: uppercase; color: #9e9ea0; margin-bottom: clamp(24px, 4vw, 40px);
}
.hero-title {
  font-weight: 600; font-size: clamp(2.8rem, 8vw, 5.5rem); line-height: 1;
  letter-spacing: -.01em; text-transform: uppercase; margin: 0;
}
.hero-line { display: block; overflow: hidden; }
.hero-line-inner { display: block; }
.hero-sub {
  margin: clamp(18px, 3vw, 32px) auto 0; max-width: 42ch;
  font-size: clamp(14px, 1.4vw, 17px); line-height: 1.6; color: #d0d0d2;
}
.hero-scroll {
  margin-top: clamp(32px, 5vh, 64px); display: flex; flex-direction: column; align-items: center; gap: 8px;
  font-size: 12px; letter-spacing: .2em; text-transform: uppercase; color: #707072;
}

/* Chat input */
.chat-wrapper { width: 100%; max-width: 580px; margin-top: clamp(28px, 4vw, 40px); }
.chat-input-shell {
  position: relative; width: 100%;
  border-radius: 16px; background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08); overflow: hidden;
}
.chat-textarea {
  width: 100%; resize: none; background: transparent; border: none; outline: none;
  color: #d0d0d8; font-size: 14px; line-height: 1.6;
  padding: 16px 16px 8px; min-height: 72px; max-height: 140px;
  font-family: 'Inter', sans-serif;
}
.chat-textarea::placeholder { color: #5a5a6a; }
.chat-actions { display: flex; align-items: center; gap: 8px; padding: 4px 10px 12px; }
.chat-send-btn {
  display: flex; align-items: center; gap: 6px;
  background: #fff; color: #000; border: none; border-radius: 24px;
  padding: 8px 20px; font-size: 14px; font-weight: 600; cursor: pointer;
  transition: all .2s ease; font-family: 'Inter', sans-serif;
}
.chat-send-btn:hover { background: #e5e5e5; transform: scale(1.02); }
.chat-send-btn:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }

.quick-prompts { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 20px; }
.quick-prompt {
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 24px; padding: 7px 16px; font-size: 12px; color: #a0a0b0;
  cursor: pointer; transition: all .2s ease; font-family: 'Inter', sans-serif;
}
.quick-prompt:hover { border-color: rgba(255,255,255,0.2); color: #fff; background: rgba(255,255,255,0.08); }

/* ===== Chat mode ===== */
.chat-header-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px clamp(20px, 4vw, 48px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.header-cta-btn {
  font-size: 13px; font-weight: 600; color: #111; background: #fff;
  border: none; border-radius: 20px; padding: 7px 18px; cursor: pointer;
  transition: all .2s ease; font-family: 'Inter', sans-serif;
}
.header-cta-btn:hover { background: #e5e5e5; }
.header-cta-btn .arrow { transition: transform .3s ease; }
.header-cta-btn:hover .arrow { transform: translate(2px,-2px); }

.chat-msg-area {
  flex: 1; overflow-y: auto; padding: 20px clamp(20px, 4vw, 48px);
  display: flex; flex-direction: column; gap: 14px;
}
.chat-msg-row { display: flex; }
.chat-msg-bubble { border-radius: 16px; padding: 10px 16px; max-width: 80%; }
.bubble-user { background: #fff; color: #111; border-bottom-right-radius: 6px; }
.bubble-ai { background: rgba(255,255,255,0.06); color: #e0dff0; border: 1px solid rgba(255,255,255,0.06); border-bottom-left-radius: 6px; }

.chat-input-bar { padding: 10px clamp(20px, 4vw, 48px) 20px; }
.chat-input-row {
  display: flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 24px; padding: 4px;
}
.chat-send-icon {
  width: 40px; height: 40px; border-radius: 50%;
  background: #fff; color: #000; border: none;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: transform .2s ease; flex-shrink: 0;
}
.chat-send-icon:hover { transform: scale(1.05); }
.chat-send-icon:disabled { opacity: 0.3; cursor: not-allowed; transform: none; }

.gen-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: #6a6a80; margin: 0 2px;
  animation: gen-float 0.9s ease-in-out infinite;
}
@keyframes gen-float {
  0%, 100% { opacity: 0.3; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-4px); }
}
</style>
