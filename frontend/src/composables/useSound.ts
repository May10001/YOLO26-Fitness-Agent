/**
 * Sound effects composable.
 * Preloads audio from /assets/ and exposes play helpers.
 */
import { ref } from 'vue'

const ready = ref(false)
const cache = new Map<string, HTMLAudioElement>()

const SFX = {
  click: '/assets/click.mp3',
  succeed: '/assets/succeed.mp3',
  milestone: '/assets/milestone.mp3',
}

// Preload all sounds
function preload(): Promise<void> {
  const promises = Object.entries(SFX).map(([key, src]) => {
    return new Promise<void>((resolve) => {
      const audio = new Audio(src)
      audio.preload = 'auto'
      audio.volume = key === 'click' ? 0.4 : 0.7
      audio.addEventListener('canplaythrough', () => resolve(), { once: true })
      audio.addEventListener('error', () => resolve()) // fail silently
      cache.set(key, audio)
    })
  })
  return Promise.all(promises).then(() => { ready.value = true })
}

function play(name: keyof typeof SFX) {
  const audio = cache.get(name)
  if (!audio) return
  audio.currentTime = 0
  audio.play().catch(() => {}) // ignore autoplay restrictions
}

// Auto-preload on first interaction
let preloaded = false
function ensurePreload() {
  if (!preloaded) {
    preloaded = true
    preload()
  }
}

export function useSound() {
  return { preload, play, ready, ensurePreload }
}
