import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  agent_type?: string
  sources?: any[]
  token_usage?: { total: number }
  latency_ms?: number
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sessionId = ref(`session_${Date.now()}`)
  const isLoading = ref(false)
  const enableRAG = ref(true)

  function addMessage(msg: ChatMessage) { messages.value.push(msg) }
  function clearMessages() { messages.value = []; sessionId.value = `session_${Date.now()}` }

  return { messages, sessionId, isLoading, enableRAG, addMessage, clearMessages }
})
