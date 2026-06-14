import { ref } from 'vue'
import type { DetectionResult, GuidanceData, CoachMessage } from '../types'

export function useWebSocket(url: string = 'ws://localhost:8002/ws/detect') {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const lastResult = ref<DetectionResult | null>(null)
  const lastGuidance = ref<GuidanceData | null>(null)
  const lastCoachMessage = ref<CoachMessage | null>(null)
  const exerciseSetConfirmed = ref(false)
  const resetConfirmed = ref(false)

  // Persist guidance for a minimum duration — ContextEngine produces
  // guidance only on occasional frames (cooldowns). Without this timer
  // every `guidance: null` frame would instantly clear the banner.
  let guidanceTimer: number | null = null
  const GUIDANCE_PERSIST_MS = 4000

  function setGuidance(g: GuidanceData | null | undefined) {
    if (g) {
      // New guidance arrived — show it and restart the persistence timer
      lastGuidance.value = g
      if (guidanceTimer) clearTimeout(guidanceTimer)
      guidanceTimer = window.setTimeout(() => {
        lastGuidance.value = null
        guidanceTimer = null
      }, GUIDANCE_PERSIST_MS)
    }
    // When g is null/undefined: do NOT clear — let the timer handle it.
    // This keeps the last guidance visible for GUIDANCE_PERSIST_MS
    // even when subsequent frames carry no guidance.
  }

  function connect() {
    ws.value = new WebSocket(url)
    ws.value.onopen = () => { connected.value = true }
    ws.value.onclose = () => { connected.value = false }
    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'result') {
        lastResult.value = data as DetectionResult
        setGuidance((data as DetectionResult).guidance)
      } else if (data.type === 'exercise_set') {
        exerciseSetConfirmed.value = true
        console.log('[WS] Exercise set confirmed:', data.exercise)
      } else if (data.type === 'coach') {
        // Proactive LLM coach push from backend
        lastCoachMessage.value = { type: 'coach', text: data.text, trigger: data.trigger || 'proactive' }
      } else if (data.type === 'reset_done') {
        resetConfirmed.value = true
        console.log('[WS] Reset confirmed')
      }
    }
  }

  function sendFrame(base64Data: string) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'frame', data: base64Data }))
    }
  }

  function setExercise(name: string) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'set_exercise', exercise: name }))
    }
  }

  function reset() {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'reset' }))
    }
    lastGuidance.value = null
    if (guidanceTimer) { clearTimeout(guidanceTimer); guidanceTimer = null }
    resetConfirmed.value = false
  }

  function disconnect() {
    ws.value?.close()
    ws.value = null
    connected.value = false
    lastResult.value = null
    lastGuidance.value = null
    lastCoachMessage.value = null
    if (guidanceTimer) { clearTimeout(guidanceTimer); guidanceTimer = null }
  }

  return { connected, lastResult, lastGuidance, lastCoachMessage,
           exerciseSetConfirmed, resetConfirmed,
           connect, sendFrame, setExercise, reset, disconnect }
}
