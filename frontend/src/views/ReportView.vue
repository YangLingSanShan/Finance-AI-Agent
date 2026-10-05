<template>
  <div class="report-view">
    <header class="page-header">
      <h2>📝 报告中心</h2>
      <button class="btn-primary" @click="generateReport">+ 生成报告</button>
    </header>
    <div class="report-list">
      <div v-for="report in reports" :key="report.id" class="report-card">
        <div class="report-header">
          <div class="report-title">{{ report.title }}</div>
          <span class="report-type-badge">{{ report.type }}</span>
        </div>
        <div class="report-meta">
          <span>📅 {{ report.date }}</span>
          <span>📊 {{ report.stock }}</span>
        </div>
        <p class="report-summary">{{ report.summary }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
const reports = ref([
  { id: 1, title: '贵州茅台深度投研报告', type: '投研', date: '2024-01-15', stock: '600519', summary: '基本面稳健，估值合理偏高，建议关注。' },
  { id: 2, title: '宁德时代⻛险评估', type: '⻛控', date: '2024-01-14', stock: '300750', summary: '市场竞争加剧，供应链⻛险可控。' },
  { id: 3, title: '科技板块投资策略', type: '策略', date: '2024-01-13', stock: '板块', summary: 'TMT板块轮动，建议均衡配置。' },
])
function generateReport() { alert('调用报告生成 Agent...') }
</script>

<style scoped>
.report-view { padding: 24px; height: 100%; overflow-y: auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 20px; color: #e0e6ed; margin: 0; }
.btn-primary { padding: 8px 20px; background: #3182ce; border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; }
.report-list { display: flex; flex-direction: column; gap: 16px; }
.report-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 20px; }
.report-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.report-title { font-size: 15px; font-weight: 600; color: #e0e6ed; }
.report-type-badge { padding: 3px 10px; background: rgba(99,179,237,0.2); border-radius: 12px; font-size: 12px; color: #63b3ed; }
.report-meta { display: flex; gap: 16px; font-size: 12px; color: #718096; margin-bottom: 10px; }
.report-summary { font-size: 13px; color: #a0aec0; margin: 0; line-height: 1.6; }
</style>
