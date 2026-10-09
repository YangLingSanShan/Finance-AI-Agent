import api from './index'
export interface KnowledgeDocument {
  id: string; title: string; category: string; status: string; chunk_count: number
  error: string | null; metadata: Record<string, string>; deduplicated?: boolean
}
export const ragApi = {
  list: () => api.get<KnowledgeDocument[], KnowledgeDocument[]>('/rag/knowledge/documents'),
  upload: (data: FormData) => api.post<KnowledgeDocument, KnowledgeDocument>('/rag/knowledge/upload', data, { headers: { 'Content-Type': undefined } }),
  remove: (id: string) => api.delete(`/rag/knowledge/documents/${encodeURIComponent(id)}`),
  reindex: (id: string) => api.post(`/rag/knowledge/documents/${encodeURIComponent(id)}/reindex`),
}
