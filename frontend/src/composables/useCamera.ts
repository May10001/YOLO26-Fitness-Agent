import { ref, onUnmounted } from 'vue'

export function useCamera() {
  const videoRef = ref<HTMLVideoElement | null>(null)
  const stream = ref<MediaStream | null>(null)
  const isActive = ref(false)

  async function start() {
    const s = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: 'user' }
    })
    stream.value = s
    if (videoRef.value) {
      videoRef.value.srcObject = s
      await videoRef.value.play()
    }
    isActive.value = true
  }

  function stop() {
    stream.value?.getTracks().forEach(t => t.stop())
    stream.value = null
    isActive.value = false
  }

  function captureFrame(): string | null {
    if (!videoRef.value || !isActive.value) return null
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.value.videoWidth
    canvas.height = videoRef.value.videoHeight
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(videoRef.value, 0, 0)
    return canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
  }

  onUnmounted(stop)

  return { videoRef, isActive, start, stop, captureFrame }
}
