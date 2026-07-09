<template>
  <div class="relative bg-[#f8f8fa] rounded-lg overflow-hidden" style="height: 180px;">
    <canvas ref="canvasRef" class="absolute inset-0 w-full h-full" />
    <div v-if="!hasKeypoints" class="absolute inset-0 flex items-center justify-center">
      <span class="text-[9px] text-faint">等待姿态数据</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps<{
  keypoints: number[][] | null
  errors: { name: string }[]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)

const SKELETON: [number, number][] = [
  [5,7],[7,9],[6,8],[8,10],[5,6],[5,11],[6,12],
  [11,12],[11,13],[13,15],[12,14],[14,16],[0,1],[0,2],[1,3],[2,4]
]

const TRUNK_BONES = new Set(['5,11','6,12','5,6','11,12'])
const hasKeypoints = ref(false)

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!
  const parent = canvas.parentElement
  if (!parent) return

  canvas.width = parent.clientWidth
  canvas.height = parent.clientHeight
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  if (!props.keypoints || props.keypoints.length === 0) {
    hasKeypoints.value = false
    return
  }

  // Check if any keypoint has non-zero coords
  const anyPoint = props.keypoints.some(([x, y]) => x !== 0 || y !== 0)
  if (!anyPoint) { hasKeypoints.value = false; return }
  hasKeypoints.value = true

  const vw = 640; const vh = 480
  const dw = canvas.width; const dh = canvas.height
  const scale = Math.min(dw / vw, dh / vh)
  const ox = (dw - vw * scale) / 2
  const oy = (dh - vh * scale) / 2
  const px = (x: number) => x * scale + ox
  const py = (y: number) => y * scale + oy

  const errorJoints = new Set<number>()
  for (const e of props.errors) {
    if ((e as any).joints && (e as any).joints.length > 0) {
      (e as any).joints.forEach((j: number) => errorJoints.add(j))
    }
  }

  // Draw bones
  for (const [i, j] of SKELETON) {
    const [x1, y1] = props.keypoints[i]
    const [x2, y2] = props.keypoints[j]
    if ((x1 === 0 && y1 === 0) || (x2 === 0 && y2 === 0)) continue
    const key = `${i},${j}`
    const isTrunk = TRUNK_BONES.has(key)
    ctx.strokeStyle = isTrunk ? '#f97316' : '#38D6B2'
    ctx.lineWidth = isTrunk ? 2.5 : 2
    ctx.beginPath()
    ctx.moveTo(px(x1), py(y1))
    ctx.lineTo(px(x2), py(y2))
    ctx.stroke()
  }

  // Draw joints (green, red for errors)
  for (let i = 0; i < props.keypoints.length; i++) {
    const [x, y] = props.keypoints[i]
    if (x === 0 && y === 0) continue
    const isErr = errorJoints.has(i)
    ctx.fillStyle = isErr ? '#ef4444' : '#38D6B2'
    ctx.beginPath()
    ctx.arc(px(x), py(y), isErr ? 5 : 3.5, 0, Math.PI * 2)
    ctx.fill()
  }
}

watch(() => [props.keypoints, props.errors], () => nextTick(draw), { deep: true })
onMounted(() => nextTick(draw))
</script>
