import { ref } from 'vue'
import type { DetectionResult } from '../types'

export function useWebSocket(url: string = 'ws://localhost:8000/ws/detect') {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const lastResult = ref<DetectionResult | null>(null)

  function connect() {
    ws.value = new WebSocket(url)
    ws.value.onopen = () => { connected.value = true }
    ws.value.onclose = () => { connected.value = false }
    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'result') {
        lastResult.value = data as DetectionResult
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
  }

  function disconnect() {
    ws.value?.close()
    ws.value = null
    connected.value = false
  }

  return { connected, lastResult, connect, sendFrame, setExercise, reset, disconnect }
}
