import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLLMOpsStore = defineStore('llmops', () => {
  const metrics = ref<any>(null)
  const dailyStats = ref<any[]>([])
  const recentCalls = ref<any[]>([])

  function setMetrics(data: any) { metrics.value = data }
  function setDailyStats(data: any[]) { dailyStats.value = data }
  function setRecentCalls(data: any[]) { recentCalls.value = data }

  return { metrics, dailyStats, recentCalls, setMetrics, setDailyStats, setRecentCalls }
})
