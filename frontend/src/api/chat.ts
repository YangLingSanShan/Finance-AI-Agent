import apiClient from './index'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  agent_type?: string
  sources?: Array<{ content: string; score: number }>
  token_usage?: { total: number }
  latency_ms?: number
  timestamp?: string
}

export interface ChatRequest {
  session_id: string
  message: string
  agent_type?: string
  stream: boolean
  enable_rag: boolean
}

export interface ChatResponse {
  session_id: string
  message: string
  agent_type: string
  sources?: Array<{ content: string; score: number }>
  token_usage?: { total: number }
  latency_ms?: number
}

export const chatApi = {
  send: (data: ChatRequest) => apiClient.post<ChatResponse>('/chat', data),
}

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'
