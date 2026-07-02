<template>
  <div
    ref="root"
    class="entry-root"
    :class="{ leaving }"
    @click="onClick"
  >
    <div ref="sky" class="entry-sky" />
    <div ref="grid" class="entry-grid" />
    <div ref="horizon" class="entry-horizon" />
    <canvas ref="canvas" class="entry-canvas" />
    <div ref="spot" class="entry-spot" />

    <div class="entry-content">
      <h1 ref="title" class="entry-title">ForMAI</h1>
      <p ref="sub" class="entry-sub">你的专属 AI 健身教练</p>
      <div ref="enter" class="entry-enter">点击进入</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const emit = defineEmits<{ (e: 'enter'): void }>()

const root = ref<HTMLElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const sky = ref<HTMLElement | null>(null)
const grid = ref<HTMLElement | null>(null)
const horizon = ref<HTMLElement | null>(null)
const spot = ref<HTMLElement | null>(null)
const title = ref<HTMLElement | null>(null)
const sub = ref<HTMLElement | null>(null)
const enter = ref<HTMLElement | null>(null)
const leaving = ref(false)

interface Pt { x: number; y: number; vx: number; vy: number; r: number; lit: boolean; order: number }

let W = 0, H = 0
let pts: Pt[] = []
const mouse = { x: -999, y: -999 }
let raf = 0
const timers: number[] = []
let intervals: number[] = []
const reduced = typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function resize() {
  const c = canvas.value; if (!c) return
  W = c.width = window.innerWidth
  H = c.height = window.innerHeight
}

function onMouseMove(e: MouseEvent) {
  mouse.x = e.clientX; mouse.y = e.clientY
  if (spot.value) { spot.value.style.left = e.clientX + 'px'; spot.value.style.top = e.clientY + 'px' }
}

function buildPoints() {
  const n = Math.min(85, Math.floor(window.innerWidth / 18))
  pts = []
  for (let i = 0; i < n; i++) {
    pts.push({
      x: Math.random() * W, y: Math.random() * H * 0.9,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 1.8 + 1, lit: reduced, order: Math.random(),
    })
  }
  pts.sort((a, b) => a.order - b.order)
}

function tick() {
  const c = canvas.value; if (!c) return
  const ctx = c.getContext('2d'); if (!ctx) return
  const N = pts.length
  ctx.clearRect(0, 0, W, H)
  for (let k = 0; k < N; k++) {
    const p = pts[k]; if (!p.lit) continue
    p.x += p.vx; p.y += p.vy
    const dm = Math.hypot(p.x - mouse.x, p.y - mouse.y)
    if (dm < 190 && dm > 1) { const f = (1 - dm / 190) * 1.1; p.x -= (p.x - mouse.x) / dm * f; p.y -= (p.y - mouse.y) / dm * f }
    if (p.x < 0 || p.x > W) p.vx *= -1
    if (p.y < 0 || p.y > H * 0.92) p.vy *= -1
  }
  for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
    if (!pts[i].lit || !pts[j].lit) continue
    const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y)
    if (d < 135) {
      const mx = (pts[i].x + pts[j].x) / 2, my = (pts[i].y + pts[j].y) / 2
      const near = Math.hypot(mx - mouse.x, my - mouse.y) < 160
      const a = (1 - d / 135) * (near ? 0.9 : 0.4)
      const g = ctx.createLinearGradient(pts[i].x, pts[i].y, pts[j].x, pts[j].y)
      g.addColorStop(0, `rgba(255,106,0,${a})`); g.addColorStop(1, `rgba(238,9,121,${a})`)
      ctx.strokeStyle = g; ctx.lineWidth = near ? 1.3 : 0.6
      ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[j].x, pts[j].y); ctx.stroke()
    }
  }
  for (let k = 0; k < N; k++) {
    const p = pts[k]; if (!p.lit) continue
    const near = Math.hypot(p.x - mouse.x, p.y - mouse.y) < 160
    ctx.beginPath(); ctx.arc(p.x, p.y, near ? p.r + 1 : p.r, 0, 6.28)
    ctx.fillStyle = near ? 'rgba(255,200,150,.95)' : 'rgba(255,150,90,.8)'
    ctx.shadowColor = '#ff6a00'; ctx.shadowBlur = near ? 14 : 7; ctx.fill()
  }
  ctx.shadowBlur = 0
  raf = requestAnimationFrame(tick)
}

const EASE = 'cubic-bezier(.16,1,.3,1)'

function fadeUp(el: HTMLElement | null, delay: number) {
  if (!el) return
  el.style.transform = 'translateY(24px)'
  const t = window.setTimeout(() => {
    el.style.transition = `opacity 1.2s ${EASE}, transform 1.2s ${EASE}`
    el.style.opacity = '1'; el.style.transform = 'none'
  }, delay)
  timers.push(t)
}

function runSequence() {
  if (reduced) {
    // Reduced motion: reveal everything immediately, no choreography
    ;[sky, grid, horizon, spot].forEach(r => { if (r.value) r.value.style.opacity = '1' })
    if (horizon.value) horizon.value.style.transform = 'scaleX(1)'
    ;[title, sub, enter].forEach(r => { if (r.value) r.value.style.opacity = '1' })
    return
  }
  if (sky.value) sky.value.style.opacity = '1'
  timers.push(window.setTimeout(() => {
    if (horizon.value) { horizon.value.style.opacity = '1'; horizon.value.style.transform = 'scaleX(1)' }
  }, 300))
  timers.push(window.setTimeout(() => { if (grid.value) grid.value.style.opacity = '1' }, 600))
  // Particles light up one by one to form the network
  timers.push(window.setTimeout(() => {
    let i = 0
    const iv = window.setInterval(() => { if (i >= pts.length) return clearInterval(iv); pts[i++].lit = true }, 22)
    intervals.push(iv)
  }, 900))
  fadeUp(title.value, 1500)
  fadeUp(sub.value, 1750)
  timers.push(window.setTimeout(() => {
    if (spot.value) spot.value.style.opacity = '1'
    if (enter.value) {
      enter.value.style.transition = 'opacity 1s'
      enter.value.style.opacity = '1'
      enter.value.style.animation = 'entry-breathe 2.6s ease-in-out infinite'
    }
  }, 2100))
}

function onClick(e: MouseEvent) {
  if (leaving.value) return
  leaving.value = true
  const r = document.createElement('div')
  r.className = 'entry-ripple'
  const s = Math.max(W, H) * 0.12
  r.style.width = r.style.height = s + 'px'
  r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'
  root.value?.appendChild(r)
  // Notify parent after the fade-out completes
  timers.push(window.setTimeout(() => emit('enter'), 1150))
}

onMounted(() => {
  resize()
  buildPoints()
  window.addEventListener('resize', resize)
  window.addEventListener('mousemove', onMouseMove)
  raf = requestAnimationFrame(tick)
  runSequence()
})

onUnmounted(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', resize)
  window.removeEventListener('mousemove', onMouseMove)
  timers.forEach(clearTimeout)
  intervals.forEach(clearInterval)
})
</script>

<style scoped>
.entry-root {
  position: fixed; inset: 0; z-index: 50; cursor: pointer; overflow: hidden;
  background: linear-gradient(180deg, #060608 0%, #0a0a0f 55%, #150810 100%);
  perspective: 340px;
}
.entry-root.leaving .entry-sky,
.entry-root.leaving .entry-grid,
.entry-root.leaving .entry-horizon,
.entry-root.leaving .entry-canvas,
.entry-root.leaving .entry-spot,
.entry-root.leaving .entry-content {
  opacity: 0 !important;
  transition: opacity 0.9s ease 0.25s;
}

.entry-sky {
  position: absolute; left: 0; right: 0; top: 34%; height: 26%; z-index: 1; opacity: 0;
  background: radial-gradient(ellipse at 50% 100%, rgba(255,106,0,.28), rgba(238,9,121,.1) 50%, transparent 75%);
  transition: opacity 1.1s ease;
}
.entry-horizon {
  position: absolute; left: 0; right: 0; top: 60%; height: 2px; z-index: 2;
  opacity: 0; transform: scaleX(.2);
  background: linear-gradient(90deg, transparent, #ff6a00 30%, #ee0979 70%, transparent);
  box-shadow: 0 0 34px 6px rgba(255,106,0,.45), 0 0 70px 16px rgba(238,9,121,.25);
  transition: opacity .9s ease, transform 1.2s cubic-bezier(.16,1,.3,1);
}
.entry-grid {
  position: absolute; left: -50%; right: -50%; top: 60%; bottom: -10%; z-index: 1; opacity: 0;
  background-image: linear-gradient(rgba(255,106,0,.22) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(238,9,121,.16) 1px, transparent 1px);
  background-size: 72px 72px;
  transform: rotateX(74deg) translateZ(-40px); transform-origin: top center;
  animation: entry-gridmove 5s linear infinite; transition: opacity 1.3s ease .2s;
  -webkit-mask-image: linear-gradient(180deg, transparent, #000 35%);
  mask-image: linear-gradient(180deg, transparent, #000 35%);
}
@keyframes entry-gridmove { from { background-position: 0 0; } to { background-position: 0 72px; } }

.entry-canvas { position: absolute; inset: 0; z-index: 3; }
.entry-spot {
  position: absolute; width: 480px; height: 480px; border-radius: 50%; z-index: 2;
  pointer-events: none; transform: translate(-50%, -50%); opacity: 0; transition: opacity .6s ease;
  background: radial-gradient(circle, rgba(255,138,61,.16), rgba(238,9,121,.06) 40%, transparent 70%);
}

.entry-content {
  position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; z-index: 5; pointer-events: none; padding-bottom: 6vh;
}
.entry-title {
  font-size: clamp(2.2rem, 7vw, 5.5rem); font-weight: 800; letter-spacing: .04em; opacity: 0;
  background: linear-gradient(90deg, #fff 10%, #ffcaa6 45%, #ff6a00 70%, #ee0979 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  text-shadow: 0 0 60px rgba(255,106,0,.25); margin: 0;
}
.entry-sub {
  margin: 1.2rem 0 0; font-size: clamp(.85rem, 1.6vw, 1.15rem); letter-spacing: .5em; opacity: 0;
  color: rgba(255,255,255,.55); font-weight: 300; padding-left: .5em;
}
.entry-enter {
  margin-top: 20vh; font-size: clamp(1rem, 2.2vw, 1.5rem); font-weight: 500; opacity: 0;
  letter-spacing: .35em; padding-left: .35em; color: #fff;
}

:deep(.entry-ripple) {
  position: absolute; border-radius: 50%; z-index: 20; pointer-events: none;
  transform: translate(-50%, -50%) scale(0);
  background: radial-gradient(circle, rgba(255,138,61,.9), rgba(238,9,121,.5) 40%, transparent 70%);
  animation: entry-ripple 1.1s cubic-bezier(.16,1,.3,1) forwards;
}
@keyframes entry-ripple { to { transform: translate(-50%, -50%) scale(28); opacity: 0; } }
@keyframes entry-breathe {
  0%, 100% { opacity: .25; text-shadow: 0 0 8px rgba(255,255,255,.1); }
  50%      { opacity: 1;   text-shadow: 0 0 24px rgba(255,138,61,.7), 0 0 48px rgba(238,9,121,.4); }
}

@media (prefers-reduced-motion: reduce) {
  .entry-grid { animation: none; }
  .entry-enter { animation: none !important; opacity: .8 !important; }
}
</style>

