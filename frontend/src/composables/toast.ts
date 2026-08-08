import { reactive } from 'vue'

export interface ToastMessage {
  id: number
  text: string
  tone: 'success' | 'error'
}

const messages = reactive<ToastMessage[]>([])
let nextId = 1

export function useToast() {
  function show(text: string, tone: ToastMessage['tone'] = 'success') {
    const id = nextId++
    messages.push({ id, text, tone })
    window.setTimeout(() => dismiss(id), 3600)
  }

  function dismiss(id: number) {
    const index = messages.findIndex((message) => message.id === id)
    if (index >= 0) messages.splice(index, 1)
  }

  return { messages, show, dismiss }
}
