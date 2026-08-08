<script setup lang="ts">
import { useToast } from '@/composables/toast'

const { messages, dismiss } = useToast()
</script>

<template>
  <div class="toast-region" aria-live="polite" aria-atomic="false">
    <div v-for="message in messages" :key="message.id" class="toast" :class="`toast-${message.tone}`">
      <span aria-hidden="true">{{ message.tone === 'success' ? '✓' : '!' }}</span>
      <p>{{ message.text }}</p>
      <button type="button" aria-label="关闭提示" @click="dismiss(message.id)">×</button>
    </div>
  </div>
</template>
