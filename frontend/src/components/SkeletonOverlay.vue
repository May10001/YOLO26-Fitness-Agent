<template>
  <canvas ref="canvasRef" class="absolute inset-0 w-full h-full pointer-events-none" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import type { ErrorData } from '../types'

const props = defineProps<{
  keypoints: number[][] | null
  errors: ErrorData[]
  videoWidth: number
  videoHeight: number
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)

const SKELETON: [number, number][] = [
  [5,7],[7,9],[6,8],[8,10],[5,6],[5,11],[6,12],
  [11,12],[11,13],[13,15],[12,14],[14,16],[0,1],[0,2],[1,3],[2,4]
]

const ERROR_JOINTS = new Set([13, 14, 15, 16])

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !props.keypoints) return
  const ctx = canvas.getContext('2d')!
  canvas.width = canvas.clientWidth
  canvas.height = canvas.clientHeight
  const scaleX = canvas.width / props.videoWidth
  const scaleY = canvas.height / props.videoHeight
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  for (const [i, j] of SKELETON) {
    const [x1, y1] = props.keypoints[i]
    const [x2, y2] = props.keypoints[j]
    if ((x1 === 0 && y1 === 0) || (x2 === 0 && y2 === 0)) continue
    const gradient = ctx.createLinearGradient(x1*scaleX, y1*scaleY, x2*scaleX, y2*scaleY)
    gradient.addColorStop(0, 'rgba(255,106,0,0.7)')
    gradient.addColorStop(1, 'rgba(238,9,121,0.5)')
    ctx.strokeStyle = gradient
    ctx.lineWidth = 2
    ctx.shadowColor = 'rgba(255,106,0,0.3)'
    ctx.shadowBlur = 6
    ctx.beginPath()
    ctx.moveTo(x1 * scaleX, y1 * scaleY)
    ctx.lineTo(x2 * scaleX, y2 * scaleY)
    ctx.stroke()
  }

  const hasKneeError = props.errors.some(e => e.name.includes('膝盖'))
  for (let i = 0; i < props.keypoints.length; i++) {
    const [x, y] = props.keypoints[i]
    if (x === 0 && y === 0) continue
    const isError = hasKneeError && ERROR_JOINTS.has(i)
    ctx.shadowColor = isError ? '#ff4d4d' : '#ff6a00'
    ctx.shadowBlur = isError ? 16 : 10
    ctx.fillStyle = isError ? '#ff4d4d' : '#ff6a00'
    ctx.beginPath()
    ctx.arc(x * scaleX, y * scaleY, isError ? 7 : 5, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.shadowBlur = 0
}

watch(() => props.keypoints, draw)
onMounted(draw)
</script>
