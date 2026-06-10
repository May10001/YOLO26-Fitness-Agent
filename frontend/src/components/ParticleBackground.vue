<template>
  <div class="fixed inset-0 z-0 pointer-events-none">
    <div
      v-for="p in particles"
      :key="p.id"
      class="absolute rounded-full"
      :class="isTraining ? 'animate-float-fast' : 'animate-float'"
      :style="{
        width: p.size + 'px',
        height: p.size + 'px',
        background: p.color,
        top: p.top + '%',
        left: p.left + '%',
        animationDelay: p.delay + 's',
      }"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{ isTraining: boolean }>()

const particles = [
  { id: 1, size: 4, color: 'rgba(255,106,0,0.4)', top: 20, left: 15, delay: 0 },
  { id: 2, size: 3, color: 'rgba(238,9,121,0.3)', top: 60, left: 25, delay: 2 },
  { id: 3, size: 5, color: 'rgba(255,106,0,0.3)', top: 30, left: 75, delay: 4 },
  { id: 4, size: 3, color: 'rgba(238,9,121,0.4)', top: 70, left: 85, delay: 1 },
  { id: 5, size: 4, color: 'rgba(255,106,0,0.3)', top: 80, left: 45, delay: 3 },
  { id: 6, size: 6, color: 'rgba(238,9,121,0.2)', top: 10, left: 55, delay: 5 },
  { id: 7, size: 3, color: 'rgba(255,106,0,0.5)', top: 45, left: 90, delay: 6 },
]
</script>
