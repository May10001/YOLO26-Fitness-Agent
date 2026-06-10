import { ref, onUnmounted } from 'vue'

export function useCamera() {
  const stream = ref<MediaStream | null>(null)
  const isActive = ref(false)
  let hiddenVideo: HTMLVideoElement | null = null

  async function start() {
    const s = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: 'user' }
    })
    stream.value = s
    hiddenVideo = document.createElement('video')
    hiddenVideo.srcObject = s
    hiddenVideo.muted = true
    hiddenVideo.playsInline = true
    await hiddenVideo.play()
    isActive.value = true
  }

  function stop() {
    stream.value?.getTracks().forEach(t => t.stop())
    stream.value = null
    isActive.value = false
    hiddenVideo = null
  }

  function captureFrame(): string | null {
    if (!hiddenVideo || !isActive.value) return null
    const canvas = document.createElement('canvas')
    canvas.width = hiddenVideo.videoWidth
    canvas.height = hiddenVideo.videoHeight
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(hiddenVideo, 0, 0)
    return canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
  }

  onUnmounted(stop)

  return { stream, isActive, start, stop, captureFrame }
}
