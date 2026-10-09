import apiClient from './index'

export interface LLMOpsMetrics {
  all_time: { total_calls: number; total_tokens: number; total_cost_usd: number; avg_latency_ms: number; success_rate: number }
  today: { calls: number; tokens: number; cost_usd: number; avg_latency_ms: number; success_rate: number }
}

export interface DailyStats {
  date: string; calls: number; tokens: number; cost_usd: number; avg_latency_ms: number; success_rate: number
}

export interface RecentCall {
  call_id: string; model: string; tokens: number; latency_ms: number; cost_usd: number
  success: boolean; error?: string; timestamp: string
}

export const llmopsApi = {
  getMetrics: (days = 7) => apiClient.get<LLMOpsMetrics, LLMOpsMetrics>('/llmops/metrics', { params: { days } }),
  getDailyStats: (days = 30) => apiClient.get<{ daily_stats: DailyStats[] }, { daily_stats: DailyStats[] }>('/llmops/daily', { params: { days } }),
  getRecentCalls: (limit = 50) => apiClient.get<{ recent_calls: RecentCall[] }, { recent_calls: RecentCall[] }>('/llmops/recent', { params: { limit } }),
}
