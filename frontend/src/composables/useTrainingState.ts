import { ref, computed } from 'vue'
import type { TrainingState } from '../types'

export function useTrainingState() {
  const state = ref<TrainingState>('idle')
  const startTime = ref<number>(0)
  const elapsed = ref<number>(0)
  let timer: number | null = null

  const isRunning = computed(() => state.value === 'running')
  const isIdle = computed(() => state.value === 'idle')

  function start() {
    state.value = 'running'
    startTime.value = Date.now()
    timer = window.setInterval(() => {
      elapsed.value = Math.floor((Date.now() - startTime.value) / 1000)
    }, 1000)
  }

  function pause() {
    state.value = 'paused'
    if (timer) clearInterval(timer)
  }

  function resume() {
    state.value = 'running'
    startTime.value = Date.now() - elapsed.value * 1000
    timer = window.setInterval(() => {
      elapsed.value = Math.floor((Date.now() - startTime.value) / 1000)
    }, 1000)
  }

  function stop() {
    state.value = 'idle'
    elapsed.value = 0
    if (timer) clearInterval(timer)
  }

  const formattedTime = computed(() => {
    const m = Math.floor(elapsed.value / 60)
    const s = elapsed.value % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  })

  return { state, isRunning, isIdle, elapsed, formattedTime, start, pause, resume, stop }
}
