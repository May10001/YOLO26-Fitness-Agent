<template>
  <div ref="scroller" class="entry-scroller" :class="{ leaving }">
    <!-- Fixed minimal nav (Nike: transparent, wordmark + pill CTA) -->
    <header class="entry-nav" :class="{ 'on-dark': navOnDark }">
      <div class="entry-nav-brand">
        <img v-if="navOnDark" src="/assets/logo.png" alt="ForMAI" class="entry-nav-logo" />
        <span class="entry-nav-mark font-display">ForMAI</span>
      </div>
      <button class="entry-nav-cta" type="button" @click="onEnter">
        进入训练 <span class="arrow">↗</span>
      </button>
    </header>

    <!-- ============ Section 1: Hero (dark) ============ -->
    <section class="sec sec-dark" data-nav="dark">
      <div class="sec-inner hero-inner">
        <!-- Large rotating logo on dark background -->
        <div class="hero-logo-wrap reveal">
          <img src="/assets/logo.png" alt="ForMAI" class="hero-logo" />
        </div>
        <div class="hero-eyebrow reveal">YOLO26 × QWEN2.5 · 实时动作诊断</div>
        <h1 class="hero-title font-display reveal">
          <span class="hero-line"><span class="hero-line-inner">你的专属</span></span>
          <span class="hero-line"><span class="hero-line-inner">AI 健身教练</span></span>
        </h1>
        <p class="hero-sub reveal">
          摄像头即教练。计算机视觉逐帧捕捉动作，大模型诊断根因、给出可执行的纠正指令。
        </p>
        <div class="hero-scroll reveal">
          <span>向下滚动</span>
          <span class="hero-scroll-arrow">↓</span>
        </div>
      </div>
    </section>

    <!-- ============ Section 2: 实时姿态检测 (light) ============ -->
    <section class="sec sec-light" data-nav="light">
      <div class="sec-inner two-col">
        <div class="col-text">
          <div class="sec-index">01 / 姿态引擎</div>
          <h2 class="sec-title font-display reveal">实时<br />姿态检测</h2>
          <p class="sec-body reveal">
            基于 YOLO26 的 17 关键点姿态估计，逐帧捕捉全身动作，目标 30fps 实时反馈。
            骨架叠加在画面中人体的对应位置，让每一次动作都被精确追踪。
          </p>
          <div class="stat-row reveal">
            <div class="stat"><div class="stat-num font-display">17</div><div class="stat-label">关键点</div></div>
            <div class="stat"><div class="stat-num font-display">30<span class="unit">fps</span></div><div class="stat-label">实时帧率</div></div>
            <div class="stat"><div class="stat-num font-display">10+</div><div class="stat-label">支持动作</div></div>
          </div>
        </div>
        <div class="col-visual reveal">
          <svg class="skeleton-art" viewBox="0 0 200 260" fill="none">
            <g stroke="#111" stroke-width="1.5">
              <line x1="100" y1="40" x2="100" y2="120" />
              <line x1="100" y1="60" x2="60" y2="100" />
              <line x1="100" y1="60" x2="140" y2="100" />
              <line x1="60" y1="100" x2="45" y2="150" />
              <line x1="140" y1="100" x2="155" y2="150" />
              <line x1="100" y1="120" x2="75" y2="180" />
              <line x1="100" y1="120" x2="125" y2="180" />
              <line x1="75" y1="180" x2="70" y2="240" />
              <line x1="125" y1="180" x2="130" y2="240" />
            </g>
            <g fill="#111">
              <circle cx="100" cy="32" r="10" />
              <circle cx="100" cy="60" r="4" /><circle cx="100" cy="120" r="4" />
              <circle cx="60" cy="100" r="4" /><circle cx="140" cy="100" r="4" />
              <circle cx="45" cy="150" r="4" /><circle cx="155" cy="150" r="4" />
              <circle cx="75" cy="180" r="4" /><circle cx="125" cy="180" r="4" />
            </g>
            <!-- error joints (functional red) -->
            <circle cx="70" cy="240" r="6" fill="#ff4d4d" />
            <circle cx="130" cy="240" r="6" fill="#ff4d4d" />
          </svg>
        </div>
      </div>
    </section>

    <!-- ============ Section 3: 三维度评分 (dark) ============ -->
    <section class="sec sec-dark" data-nav="dark">
      <div class="sec-inner">
        <div class="sec-index light">02 / 评分体系</div>
        <h2 class="sec-title font-display center reveal">三维度评分</h2>
        <p class="sec-body center reveal dim">
          每一次动作从三个维度量化打分，总分 100，实时反映动作质量。
        </p>
        <div class="score-grid">
          <div class="score-cell reveal">
            <div class="score-num font-display">40</div>
            <div class="score-name">关节角度</div>
            <div class="score-desc">关键关节角度与标准范围的贴合度</div>
          </div>
          <div class="score-cell reveal">
            <div class="score-num font-display">30</div>
            <div class="score-name">时序一致</div>
            <div class="score-desc">动作节奏的稳定性与流畅度</div>
          </div>
          <div class="score-cell reveal">
            <div class="score-num font-display">30</div>
            <div class="score-name">左右对称</div>
            <div class="score-desc">身体两侧发力的平衡程度</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ Section 4: LLM 智能诊断教练 (light) ============ -->
    <section class="sec sec-light" data-nav="light">
      <div class="sec-inner">
        <div class="sec-index">03 / 智能教练</div>
        <h2 class="sec-title font-display reveal">会推理的<br />AI 教练</h2>
        <p class="sec-body reveal">
          不只是报数机器。大模型先诊断根因，再给出可执行的动作 cue，并追踪指导效果。
        </p>
        <div class="step-row">
          <div class="step reveal">
            <div class="step-num font-display">诊断</div>
            <div class="step-text">从裸角度到结构化诊断快照——逐关节偏差、稳定性 σ、趋势、共现模式</div>
          </div>
          <div class="step reveal">
            <div class="step-num font-display">知识</div>
            <div class="step-text">每个动作错误配生物力学根因链 + 分层纠正 cue（外部/内部/回归训练）</div>
          </div>
          <div class="step reveal">
            <div class="step-num font-display">纠正</div>
            <div class="step-text">两段式输出：内部诊断 JSON + 面向用户的自然语言指导</div>
          </div>
          <div class="step reveal">
            <div class="step-num font-display">追踪</div>
            <div class="step-text">记住上次 cue，检测是否有效，无效则自动切换角度或升级策略</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ Section 5: RAG 问答 + AI 计划 (dark) ============ -->
    <section class="sec sec-dark" data-nav="dark">
      <div class="sec-inner two-col">
        <div class="col-text">
          <div class="sec-index light">04 / 知识与计划</div>
          <h2 class="sec-title font-display reveal">问答<br />与计划</h2>
          <p class="sec-body reveal dim">
            基于 1600+ 条健身专业知识库的 RAG 问答，动作纠正、训练规划、伤病预防随问随答。
            结合用户画像，AI 按需生成结构化训练计划。
          </p>
        </div>
        <div class="col-visual reveal">
          <div class="kb-stat">
            <div class="kb-num font-display">1600<span class="unit">+</span></div>
            <div class="kb-label">专业知识条目</div>
          </div>
          <div class="kb-tags">
            <span class="kb-tag">动作纠错</span>
            <span class="kb-tag">训练规划</span>
            <span class="kb-tag">伤病预防</span>
            <span class="kb-tag">营养建议</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ Section 6: CTA (light) ============ -->
    <section class="sec sec-light sec-cta" data-nav="light">
      <div class="sec-inner cta-inner">
        <div class="cta-eyebrow reveal">准备好了吗</div>
        <h2 class="cta-title font-display reveal">开始训练</h2>
        <button class="cta-btn reveal" type="button" @click="onEnter">
          进入训练 <span class="arrow">→</span>
        </button>
        <div class="cta-foot reveal">授权摄像头 · 选择动作 · 即刻开始</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const emit = defineEmits<{ (e: 'enter'): void }>()

const scroller = ref<HTMLElement | null>(null)
const leaving = ref(false)
const navOnDark = ref(true)   // hero is dark → nav uses light-on-dark styling

let io: IntersectionObserver | null = null
let navIo: IntersectionObserver | null = null
const timers: number[] = []

const reduced = typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function onEnter() {
  if (leaving.value) return
  leaving.value = true
  timers.push(window.setTimeout(() => emit('enter'), 650))
}

onMounted(() => {
  const root = scroller.value
  if (!root) return

  const reveals = Array.from(root.querySelectorAll('.reveal')) as HTMLElement[]

  if (reduced) {
    reveals.forEach(el => el.classList.add('in'))
  } else {
    // Reveal-on-scroll: fade + rise as each element enters the viewport
    io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add('in')
          io?.unobserve(e.target)
        }
      }
    }, { threshold: 0.18 })
    reveals.forEach(el => io!.observe(el))
  }

  // Track which section is under the nav to flip nav color (light/dark)
  const sections = Array.from(root.querySelectorAll('.sec')) as HTMLElement[]
  navIo = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting && e.intersectionRatio > 0.5) {
        navOnDark.value = (e.target as HTMLElement).dataset.nav === 'dark'
      }
    }
  }, { threshold: [0.5], rootMargin: '-60px 0px 0px 0px' })
  sections.forEach(s => navIo!.observe(s))
})

onUnmounted(() => {
  io?.disconnect()
  navIo?.disconnect()
  timers.forEach(clearTimeout)
})
</script>

<style scoped>
/* ============================================================
   Nike monochrome landing — scroll-snap sections, dark/light rhythm
   ============================================================ */
.entry-scroller {
  position: fixed; inset: 0; z-index: 50;
  overflow-y: auto; overflow-x: hidden;
  scroll-snap-type: y proximity; scroll-behavior: smooth;
  background: #fff; color: #111;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
  transition: opacity .6s ease, transform .6s ease;
}
.entry-scroller.leaving { opacity: 0; transform: scale(1.012); }

/* ---- Nav ---- */
.entry-nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 10;
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px clamp(24px, 5vw, 60px);
  transition: color .4s ease;
}
.entry-nav.on-dark { color: #fff; }
.entry-nav:not(.on-dark) { color: #111; }
.entry-nav-brand {
  display: flex; align-items: center; gap: 12px;
}
.entry-nav-logo {
  height: clamp(36px, 4vw, 52px); width: auto;
}
.entry-nav-mark {
  font-weight: 600; font-size: clamp(20px, 2.2vw, 26px);
  letter-spacing: .02em; text-transform: uppercase;
}
.entry-nav-cta {
  cursor: pointer; display: inline-flex; align-items: center; gap: .4em;
  border: 1px solid currentColor; border-radius: 30px; background: transparent;
  color: inherit; font-family: 'Inter', sans-serif; font-weight: 500; font-size: 14px;
  padding: 8px 18px; transition: background .3s ease, color .3s ease;
}
.entry-nav.on-dark .entry-nav-cta:hover { background: #fff; color: #111; }
.entry-nav:not(.on-dark) .entry-nav-cta:hover { background: #111; color: #fff; }
.entry-nav-cta .arrow { transition: transform .3s cubic-bezier(.16,1,.3,1); }
.entry-nav-cta:hover .arrow { transform: translate(2px,-2px); }

/* ---- Section shells ---- */
.sec {
  min-height: 100vh; scroll-snap-align: start;
  display: flex; align-items: center; justify-content: center;
  padding: 96px clamp(24px, 5vw, 60px);
}
.sec-dark { background: #05080C; color: #F4F7F5; }
.sec-light { background: #fff; color: #111; }
.sec-inner { width: 100%; max-width: 1080px; }

/* ---- Reveal animation ---- */
.reveal { opacity: 0; transform: translateY(26px); transition: opacity .9s cubic-bezier(.16,1,.3,1), transform .9s cubic-bezier(.16,1,.3,1); }
.reveal.in { opacity: 1; transform: none; }

/* ---- Hero ---- */
.hero-inner { text-align: center; display: flex; flex-direction: column; align-items: center; }
.hero-logo-wrap {
  margin-bottom: clamp(20px, 3vw, 36px);
}
.hero-logo {
  width: clamp(120px, 18vw, 200px); height: auto;
  filter: drop-shadow(0 0 40px rgba(56,214,178,0.25));
}
.hero-eyebrow {
  font-size: clamp(11px, 1vw, 13px); font-weight: 500; letter-spacing: .28em;
  text-transform: uppercase; color: #9e9ea0; margin-bottom: clamp(24px, 4vw, 40px);
}
.hero-title {
  font-weight: 600; font-size: clamp(3rem, 10vw, 7.5rem); line-height: 1; letter-spacing: -.01em;
  text-transform: uppercase; margin: 0;
}
.hero-line { display: block; overflow: hidden; }
.hero-line-inner { display: block; }
.hero-sub {
  margin: clamp(24px, 3.5vw, 40px) auto 0; max-width: 40ch;
  font-size: clamp(15px, 1.5vw, 18px); line-height: 1.6; color: #d0d0d2;
}
.hero-scroll {
  margin-top: clamp(48px, 8vh, 96px); display: flex; flex-direction: column; align-items: center; gap: 8px;
  font-size: 12px; letter-spacing: .2em; text-transform: uppercase; color: #707072;
}
.hero-scroll-arrow { font-size: 18px; animation: entry-bounce 2s ease-in-out infinite; }
@keyframes entry-bounce { 0%,100% { transform: translateY(0); } 50% { transform: translateY(6px); } }

/* ---- Two-column sections ---- */
.two-col { display: grid; grid-template-columns: 1.1fr .9fr; gap: clamp(32px, 6vw, 80px); align-items: center; }
.col-visual { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 24px; }
.skeleton-art { width: clamp(160px, 20vw, 220px); height: auto; }

/* ---- Section headings ---- */
.sec-index { font-size: 12px; font-weight: 500; letter-spacing: .2em; text-transform: uppercase; color: #707072; margin-bottom: 20px; }
.sec-index.light { color: #9e9ea0; }
.sec-title { font-weight: 600; font-size: clamp(2.4rem, 6vw, 4.5rem); line-height: 1.02; letter-spacing: -.01em; text-transform: uppercase; margin: 0; }
.sec-title.center { text-align: center; }
.sec-body { margin-top: 24px; max-width: 46ch; font-size: clamp(15px, 1.4vw, 17px); line-height: 1.65; color: #33312c; }
.sec-body.dim { color: #b8b8ba; }
.sec-body.center { margin-left: auto; margin-right: auto; text-align: center; }

/* ---- Stat row ---- */
.stat-row { display: flex; gap: clamp(24px, 4vw, 48px); margin-top: 40px; }
.stat-num { font-weight: 600; font-size: clamp(32px, 4vw, 48px); line-height: 1; }
.stat-num .unit { font-size: .45em; font-weight: 500; margin-left: .1em; color: #707072; }
.stat-label { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: #707072; margin-top: 8px; }

/* ---- Score grid (dark) ---- */
.score-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: #1A3B48; margin-top: clamp(40px, 6vw, 64px); border: 1px solid #1A3B48; }
.score-cell { background: #05080C; padding: clamp(28px, 4vw, 44px) clamp(20px, 3vw, 32px); text-align: center; }
.score-num { font-weight: 600; font-size: clamp(56px, 9vw, 96px); line-height: 1; }
.score-name { font-size: clamp(15px, 1.6vw, 19px); font-weight: 500; margin-top: 12px; }
.score-desc { font-size: 13px; line-height: 1.5; color: #9e9ea0; margin-top: 10px; }

/* ---- Step row (4-step diagnosis) ---- */
.step-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: #e5e5e5; margin-top: clamp(40px, 5vw, 56px); border: 1px solid #e5e5e5; }
.step { background: #fff; padding: clamp(24px, 3vw, 32px) clamp(18px, 2vw, 24px); }
.step-num { font-weight: 600; font-size: clamp(22px, 2.4vw, 30px); text-transform: uppercase; letter-spacing: -.01em; }
.step-text { font-size: 13px; line-height: 1.6; color: #707072; margin-top: 14px; }

/* ---- Knowledge base visual ---- */
.kb-stat { text-align: center; }
.kb-num { font-weight: 600; font-size: clamp(56px, 8vw, 88px); line-height: 1; }
.kb-num .unit { font-size: .5em; color: #707072; }
.kb-label { font-size: 13px; letter-spacing: .1em; text-transform: uppercase; color: #9e9ea0; margin-top: 12px; }
.kb-tags { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 28px; }
.kb-tag { border: 1px solid #153A49; border-radius: 8px; padding: 8px 18px; font-size: 13px; color: #B7C3CD; background: rgba(56,214,178,0.06); }

/* ---- CTA ---- */
.cta-inner { text-align: center; display: flex; flex-direction: column; align-items: center; }
.cta-eyebrow { font-size: 13px; letter-spacing: .28em; text-transform: uppercase; color: #707072; margin-bottom: 24px; }
.cta-title { font-weight: 600; font-size: clamp(3.2rem, 11vw, 9rem); line-height: 1; text-transform: uppercase; margin: 0 0 clamp(40px, 6vw, 64px); }
.cta-btn {
  cursor: pointer; display: inline-flex; align-items: center; gap: .5em;
  background: #111; color: #fff; border: 1px solid #111; border-radius: 30px;
  font-family: 'Inter', sans-serif; font-weight: 500; font-size: clamp(16px, 2vw, 20px);
  padding: 18px 44px; transition: opacity .3s ease;
}
.cta-btn:hover { opacity: .82; }
.cta-btn .arrow { transition: transform .3s cubic-bezier(.16,1,.3,1); }
.cta-btn:hover .arrow { transform: translateX(6px); }
.cta-foot { margin-top: 32px; font-size: 13px; letter-spacing: .06em; color: #9e9ea0; }

/* ---- Responsive ---- */
@media (max-width: 780px) {
  .two-col { grid-template-columns: 1fr; }
  .score-grid { grid-template-columns: 1fr; }
  .step-row { grid-template-columns: 1fr 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .entry-scroller { scroll-behavior: auto; }
  .hero-scroll-arrow { animation: none; }
  .reveal { transition: none; }
}
</style>
