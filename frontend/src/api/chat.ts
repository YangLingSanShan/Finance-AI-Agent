import apiClient from './index'

export interface ToolCall {
  id: string
  name: string
  success: boolean
  result?: string
  error?: string
}

export interface ChatMessage {
  report_id?: string
  role: 'user' | 'assistant'
  content: string
  agent_type?: string
  tool_calls?: ToolCall[]
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
  report_id?: string
  session_id: string
  message: string
  agent_type: string
  model: string
  tool_calls: ToolCall[]
  sources?: Array<{ content: string; score: number }>
  token_usage?: { total: number }
  latency_ms?: number
}

export const chatApi = {
  send: (data: ChatRequest) => apiClient.post<ChatResponse, ChatResponse>('/chat', data),
}

export { API_BASE } from './index'
