<template>
  <canvas ref="canvasRef" class="absolute inset-0 w-full h-full pointer-events-none" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import type { ErrorData } from '../types'

const props = defineProps<{
  keypoints: number[][] | null
  errors: ErrorData[]
  videoWidth: number
  videoHeight: number
  /** 'contain' letterboxes (landing/pose viewer); 'cover' matches video object-cover (training). */
  fit?: 'contain' | 'cover'
  /** 'full' = whole skeleton; 'errors-only' = only error joints; 'hidden' = nothing. */
  mode?: 'full' | 'errors-only' | 'hidden'
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)

// COCO-17 skeleton bone pairs
const SKELETON: [number, number][] = [
  [5,7],[7,9],[6,8],[8,10],[5,6],[5,11],[6,12],
  [11,12],[11,13],[13,15],[12,14],[14,16],[0,1],[0,2],[1,3],[2,4]
]

// Map error-name keywords → COCO joint indices to highlight
const ERROR_KEYWORD_JOINTS: { kw: string; joints: number[] }[] = [
  { kw: '膝', joints: [13, 14] },
  { kw: '肘', joints: [7, 8] },
  { kw: '肩', joints: [5, 6] },
  { kw: '腰', joints: [11, 12] },
  { kw: '背', joints: [11, 12] },
  { kw: '髋', joints: [11, 12] },
  { kw: '躯干', joints: [11, 12] },
  { kw: '摆动', joints: [11, 12] },
  { kw: '晃动', joints: [11, 12] },
  { kw: '后仰', joints: [11, 12] },
  { kw: '颈', joints: [0] },
]

/** Compute the set of joint indices flagged by current errors. */
function errorJointSet(): Set<number> {
  const s = new Set<number>()
  for (const e of props.errors) {
    for (const { kw, joints } of ERROR_KEYWORD_JOINTS) {
      if (e.name.includes(kw)) joints.forEach(j => s.add(j))
    }
  }
  return s
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!
  const parent = canvas.parentElement
  if (!parent) return

  const dw = parent.clientWidth
  const dh = parent.clientHeight
  canvas.width = dw
  canvas.height = dh
  ctx.clearRect(0, 0, dw, dh)

  const mode = props.mode ?? 'full'
  if (mode === 'hidden' || !props.keypoints) return

  // ---- Alignment: map raw video-frame coords → displayed canvas coords ----
  const vw = props.videoWidth, vh = props.videoHeight
  let scaleX: number, scaleY: number, offsetX = 0, offsetY = 0

  if (props.fit === 'cover') {
    // object-cover: fill the container, cropping overflow. scale = max ratio.
    const scale = Math.max(dw / vw, dh / vh)
    scaleX = scaleY = scale
    offsetX = (dw - vw * scale) / 2   // negative → cropped left/right
    offsetY = (dh - vh * scale) / 2   // negative → cropped top/bottom
  } else {
    // contain: letterbox. scale = min ratio, centered.
    const containerAspect = dw / Math.max(dh, 1)
    const videoAspect = vw / Math.max(vh, 1)
    if (containerAspect > videoAspect) {
      scaleY = scaleX = dh / vh
      offsetX = (dw - vw * scaleX) / 2
    } else {
      scaleX = scaleY = dw / vw
      offsetY = (dh - vh * scaleY) / 2
    }
  }
  const px = (x: number) => x * scaleX + offsetX
  const py = (y: number) => y * scaleY + offsetY

  const errorJoints = errorJointSet()
  const showBones = mode === 'full'

  // ---- Bones (only in full mode) ----
  if (showBones) {
    for (const [i, j] of SKELETON) {
      const [x1, y1] = props.keypoints[i]
      const [x2, y2] = props.keypoints[j]
      if ((x1 === 0 && y1 === 0) || (x2 === 0 && y2 === 0)) continue
      const g = ctx.createLinearGradient(px(x1), py(y1), px(x2), py(y2))
      g.addColorStop(0, 'rgba(255,106,0,0.75)')
      g.addColorStop(1, 'rgba(238,9,121,0.55)')
      ctx.strokeStyle = g
      ctx.lineWidth = 2.5
      ctx.shadowColor = 'rgba(255,106,0,0.35)'
      ctx.shadowBlur = 6
      ctx.beginPath()
      ctx.moveTo(px(x1), py(y1))
      ctx.lineTo(px(x2), py(y2))
      ctx.stroke()
    }
  }

  // ---- Joints ----
  for (let i = 0; i < props.keypoints.length; i++) {
    const [x, y] = props.keypoints[i]
    if (x === 0 && y === 0) continue
    const isError = errorJoints.has(i)

    // errors-only mode: skip non-error joints entirely
    if (!showBones && !isError) continue

    ctx.shadowColor = isError ? '#ff4d4d' : '#4488ff'
    ctx.shadowBlur = isError ? 16 : 10
    ctx.fillStyle = isError ? '#ff4d4d' : '#4488ff'
    ctx.beginPath()
    ctx.arc(px(x), py(y), isError ? 8 : 5, 0, Math.PI * 2)
    ctx.fill()

    // Pulsing ring around error joints for emphasis
    if (isError) {
      ctx.shadowBlur = 0
      ctx.strokeStyle = 'rgba(255,77,77,0.5)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(px(x), py(y), 14, 0, Math.PI * 2)
      ctx.stroke()
    }
  }
  ctx.shadowBlur = 0
}

watch(() => [props.keypoints, props.mode, props.errors], () => nextTick(draw), { deep: true })
onMounted(() => nextTick(draw))
</script>
