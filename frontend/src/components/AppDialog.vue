<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

defineProps<{ title: string; description?: string; busy?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const closeButton = ref<HTMLButtonElement | null>(null)

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  await nextTick()
  closeButton.value?.focus()
})
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="dialog-backdrop" @click.self="$emit('close')">
    <section class="dialog-card" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
      <header class="dialog-header">
        <div>
          <h2 id="dialog-title">{{ title }}</h2>
          <p v-if="description">{{ description }}</p>
        </div>
        <button ref="closeButton" class="icon-button" type="button" aria-label="关闭" :disabled="busy" @click="$emit('close')">×</button>
      </header>
      <slot />
    </section>
  </div>
</template>
