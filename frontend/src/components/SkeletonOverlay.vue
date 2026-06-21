<template>
  <canvas ref="canvasRef" class="absolute inset-0 w-full h-full" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import type { ErrorData } from '../types'

const props = defineProps<{
  keypoints: number[][] | null
  errors: ErrorData[]
  videoWidth: number
  videoHeight: number
  contain?: boolean
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

  const parent = canvas.parentElement
  if (!parent) return

  const dw = parent.clientWidth
  const dh = parent.clientHeight
  canvas.width = dw
  canvas.height = dh

  let scaleX: number, scaleY: number
  let offsetX = 0, offsetY = 0

  if (props.contain) {
    const containerAspect = dw / Math.max(dh, 1)
    const videoAspect = props.videoWidth / Math.max(props.videoHeight, 1)
    if (containerAspect > videoAspect) {
      scaleY = dh / props.videoHeight
      scaleX = scaleY
      offsetX = (dw - props.videoWidth * scaleX) / 2
    } else {
      scaleX = dw / props.videoWidth
      scaleY = scaleX
      offsetY = (dh - props.videoHeight * scaleY) / 2
    }
  } else {
    scaleX = dw / props.videoWidth
    scaleY = dh / props.videoHeight
  }

  ctx.clearRect(0, 0, dw, dh)

  for (const [i, j] of SKELETON) {
    const [x1, y1] = props.keypoints[i]
    const [x2, y2] = props.keypoints[j]
    if ((x1 === 0 && y1 === 0) || (x2 === 0 && y2 === 0)) continue
    const gradient = ctx.createLinearGradient(
      x1 * scaleX + offsetX, y1 * scaleY + offsetY,
      x2 * scaleX + offsetX, y2 * scaleY + offsetY,
    )
    gradient.addColorStop(0, 'rgba(255,106,0,0.7)')
    gradient.addColorStop(1, 'rgba(238,9,121,0.5)')
    ctx.strokeStyle = gradient
    ctx.lineWidth = 2
    ctx.shadowColor = 'rgba(255,106,0,0.3)'
    ctx.shadowBlur = 6
    ctx.beginPath()
    ctx.moveTo(x1 * scaleX + offsetX, y1 * scaleY + offsetY)
    ctx.lineTo(x2 * scaleX + offsetX, y2 * scaleY + offsetY)
    ctx.stroke()
  }

  const hasKneeError = props.errors.some(e => e.name.includes('膝盖'))
  for (let i = 0; i < props.keypoints.length; i++) {
    const [x, y] = props.keypoints[i]
    if (x === 0 && y === 0) continue
    const isError = hasKneeError && ERROR_JOINTS.has(i)
    ctx.shadowColor = isError ? '#ff4d4d' : '#4488ff'
    ctx.shadowBlur = isError ? 16 : 10
    ctx.fillStyle = isError ? '#ff4d4d' : '#4488ff'
    ctx.beginPath()
    ctx.arc(x * scaleX + offsetX, y * scaleY + offsetY, isError ? 7 : 5, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.shadowBlur = 0
}

watch(() => props.keypoints, () => nextTick(draw))
onMounted(() => nextTick(draw))
</script>
