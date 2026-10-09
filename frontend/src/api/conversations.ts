import apiClient from './index'
import type { ChatMessage } from './chat'

export interface Conversation {
  id: string
  title: string
  archived: boolean
  created_at: string
  updated_at: string
}
export interface ConversationDetail extends Conversation {
  messages: (ChatMessage & { model?: string })[]
}
export const conversationsApi = {
  list: (archived: boolean) => apiClient.get<Conversation[], Conversation[]>('/conversations', { params: { archived } }),
  create: () => apiClient.post<Conversation, Conversation>('/conversations'),
  get: (id: string) => apiClient.get<ConversationDetail, ConversationDetail>(`/conversations/${encodeURIComponent(id)}`),
  archive: (id: string, archived: boolean) => apiClient.patch<Conversation, Conversation>(`/conversations/${encodeURIComponent(id)}`, { archived }),
  delete: (id: string) => apiClient.delete(`/conversations/${encodeURIComponent(id)}`),
}
