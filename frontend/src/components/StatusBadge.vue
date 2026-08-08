<script setup lang="ts">
defineProps<{ status?: string | null; label?: string }>()
</script>

<template>
  <span class="badge" :class="`badge-${status || 'unknown'}`">{{ label || status || '暂无状态' }}</span>
</template>
