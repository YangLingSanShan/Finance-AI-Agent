<template>
  <div class="llmops-view">
    <header class="page-header">
      <h2>⚙ LLMOps 监控面板</h2>
      <button class="btn-refresh" @click="loadData">🔄 刷新</button>
    </header>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">今日调用次数</div>
        <div class="metric-value">{{ metrics?.today?.calls || 0 }}</div>
        <div class="metric-sub">成功率 {{ metrics?.today?.success_rate || 0 }}%</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">今日 Token 消耗</div>
        <div class="metric-value">{{ formatNumber(metrics?.today?.tokens || 0) }}</div>
        <div class="metric-sub">平均延迟 {{ metrics?.today?.avg_latency_ms || 0 }}ms</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">今日成本</div>
        <div class="metric-value">${{ (metrics?.today?.cost_usd || 0).toFixed(4) }}</div>
        <div class="metric-sub">累计 ${{ (metrics?.all_time?.total_cost_usd || 0).toFixed(4) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">累计调用</div>
        <div class="metric-value">{{ formatNumber(metrics?.all_time?.total_calls || 0) }}</div>
        <div class="metric-sub">累计 Token {{ formatNumber(metrics?.all_time?.total_tokens || 0) }}</div>
      </div>
    </div>

    <div class="section">
      <h3 class="section-title">📋 最近调用记录</h3>
      <div class="table-wrapper">
        <table class="data-table">
          <thead><tr><th>时间</th><th>模型</th><th>Token数</th><th>延迟</th><th>成本</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="call in recentCalls" :key="call.call_id">
              <td>{{ call.timestamp }}</td>
              <td><code>{{ call.model }}</code></td>
              <td>{{ formatNumber(call.tokens) }}</td>
              <td>{{ call.latency_ms }}ms</td>
              <td>${{ call.cost_usd.toFixed(6) }}</td>
              <td><span :class="['status-tag', call.success ? 'success' : 'error']">{{ call.success ? '✅ 成功' : '❌ 失败' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h3 class="section-title">📈 每日调用趋势（前14天）</h3>
      <div class="bar-chart">
        <div v-for="day in dailyStats.slice(-14)" :key="day.date" class="bar-item">
          <div class="bar" :style="{ height: (day.calls / maxDailyCalls * 100) + '%' }" :title="day.date + ': ' + day.calls + '次'">
          <div class="bar-label">{{ day.date.slice(5) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { llmopsApi, type LLMOpsMetrics, type DailyStats, type RecentCall } from '@/api/llmops'

const metrics = ref<LLMOpsMetrics>()
const recentCalls = ref<RecentCall[]>([])
const dailyStats = ref<DailyStats[]>([])

const maxDailyCalls = computed(() => {
  if (!dailyStats.value.length) return 1
  return Math.max(...dailyStats.value.map(d => d.calls), 1)
})

function formatNumber(n: number) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toString()
}

async function loadData() {
  try {
    const [m, r, d] = await Promise.all([
      llmopsApi.getMetrics(7),
      llmopsApi.getRecentCalls(30),
      llmopsApi.getDailyStats(30),
    ])
    metrics.value = m
    recentCalls.value = r.recent_calls
    dailyStats.value = d.daily_stats
  } catch (e) { console.error('LLMOps load error:', e) }
}

onMounted(loadData)
</script>

<style scoped>
.llmops-view { padding: 24px; height: 100%; overflow-y: auto; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.page-header h2 { font-size: 20px; font-weight: 600; color: #e0e6ed; margin: 0; }
.btn-refresh { padding: 8px 16px; background: rgba(99,179,237,0.15); border: 1px solid rgba(99,179,237,0.3); border-radius: 8px; color: #63b3ed; cursor: pointer; font-size: 13px; }
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.metric-card { background: linear-gradient(135deg, rgba(99,179,237,0.1), rgba(99,179,237,0.05)); border: 1px solid rgba(99,179,237,0.2); border-radius: 12px; padding: 20px; text-align: center; }
.metric-label { font-size: 12px; color: #718096; margin-bottom: 8px; }
.metric-value { font-size: 28px; font-weight: 700; color: #63b3ed; margin-bottom: 4px; }
.metric-sub { font-size: 11px; color: #4a5568; }
.section { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.section-title { font-size: 15px; font-weight: 600; color: #e0e6ed; margin: 0 0 16px; }
.table-wrapper { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th { text-align: left; padding: 10px 12px; color: #718096; font-weight: 500; border-bottom: 1px solid rgba(255,255,255,0.08); }
.data-table td { padding: 10px 12px; color: #a0aec0; border-bottom: 1px solid rgba(255,255,255,0.04); }
.data-table code { font-size: 12px; color: #68d391; background: rgba(104,211,145,0.1); padding: 2px 6px; border-radius: 4px; }
.status-tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.status-tag.success { background: rgba(104,211,145,0.15); color: #68d391; }
.status-tag.error { background: rgba(252,129,129,0.15); color: #fc8181; }
.bar-chart { height: 160px; display: flex; align-items: flex-end; gap: 6px; }
.bar-item { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
.bar { width: 100%; background: linear-gradient(to top, #3182ce, #63b3ed); border-radius: 4px 4px 0 0; min-height: 4px; transition: height 0.3s; opacity: 0.8; }
.bar:hover { opacity: 1; }
.bar-label { font-size: 10px; color: #4a5568; margin-top: 4px; }
</style>
