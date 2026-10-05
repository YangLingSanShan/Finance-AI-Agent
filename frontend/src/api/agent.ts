import apiClient from './index'

export const agentApi = {
  invoke: (data: { session_id: string; query: string; agent_types?: string[]; parallel?: boolean }) =>
    apiClient.post('/agent/invoke', data),
  getMemory: (sessionId: string) => apiClient.get(`/agent/memory/${sessionId}`),
  clearMemory: (sessionId: string) => apiClient.delete(`/agent/memory/${sessionId}`),
  listTypes: () => apiClient.get('/agent/types'),
}
