import apiClient from './index'

export interface Report {
  id: string
  title: string
  stock_code: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  error: string | null
  content?: string
  model?: string
  run_id?: string
  session_id?: string
  sources?: Array<{ citation?: string; label?: string; content: string; metadata?: Record<string, unknown> }>
}
export const reportsApi = {
  list: () => apiClient.get<Report[], Report[]>('/reports'),
  get: (id: string) => apiClient.get<Report, Report>(`/reports/${encodeURIComponent(id)}`),
  create: (stock_code: string, query: string, enable_rag: boolean) =>
    apiClient.post<Report, Report>('/reports', { stock_code, query, enable_rag }),
  delete: (id: string) => apiClient.delete(`/reports/${encodeURIComponent(id)}`),
  download: (id: string) => apiClient.get<Blob, Blob>(`/reports/${encodeURIComponent(id)}/download`, { responseType: 'blob' }),
}
