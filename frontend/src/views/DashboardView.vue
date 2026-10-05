<template>
  <div class="dashboard-view">
    <header class="page-header"><h2>📊 金融数据看板</h2></header>
    <div class="stock-cards">
      <div v-for="stock in mockStocks" :key="stock.code" class="stock-card">
        <div class="stock-top">
          <div class="stock-name">{{ stock.name }}</div>
          <div class="stock-code">{{ stock.code }}</div>
        </div>
        <div class="stock-price">¥{{ stock.price.toFixed(2) }}</div>
        <div class="stock-change" :class="stock.changePct >= 0 ? 'up' : 'down'">
          {{ stock.changePct >= 0 ? '+' : '' }}{{ stock.changePct.toFixed(2) }}%
        </div>
        <div class="stock-vol">成交量: {{ (stock.volume / 100000000).toFixed(2) }}亿</div>
      </div>
    </div>
    <div class="dashboard-bottom">
      <div class="panel">
        <h3>系统架构说明</h3>
        <div class="arch-list">
          <div class="arch-item">🔷 <strong>Agent 编排层</strong>：多 Agent 协同，意图分类，任务调度</div>
          <div class="arch-item">🔷 <strong>RAG 知识增强</strong>：混合检索，向量召回，GRAG 生成增强</div>
          <div class="arch-item">🔷 <strong>LLM 大模型层</strong>：Qwen/DeepSeek，Function Calling，工具调用</div>
          <div class="arch-item">🔷 <strong>LLMOps 监控</strong>：Token 计量，成本追踪，Prometheus 指标</div>
          <div class="arch-item">🔷 <strong>DataOps 数据层</strong>：Prefect 管道，ETL 编排，数据质量校验</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
const mockStocks = ref([
  { code: '600519', name: '贵州茅台', price: 1688.00, changePct: 1.25, volume: 2800000000 },
  { code: '000858', name: '五粮液', price: 142.50, changePct: -0.83, volume: 1200000000 },
  { code: '300750', name: '宁德时代', price: 198.30, changePct: 2.15, volume: 3500000000 },
  { code: '601318', name: '中国平安', price: 45.80, changePct: 0.55, volume: 2200000000 },
])
</script>

<style scoped>
.dashboard-view { padding: 24px; height: 100%; overflow-y: auto; }
.page-header h2 { font-size: 20px; font-weight: 600; color: #e0e6ed; margin: 0 0 24px; }
.stock-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stock-card { background: linear-gradient(135deg, rgba(99,179,237,0.1), rgba(99,179,237,0.03)); border: 1px solid rgba(99,179,237,0.2); border-radius: 12px; padding: 20px; }
.stock-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.stock-name { font-size: 15px; font-weight: 600; color: #e0e6ed; }
.stock-code { font-size: 12px; color: #718096; }
.stock-price { font-size: 24px; font-weight: 700; color: #e0e6ed; margin-bottom: 6px; }
.stock-change { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.stock-change.up { color: #fc8181; }
.stock-change.down { color: #68d391; }
.stock-vol { font-size: 12px; color: #4a5568; }
.panel { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 20px; }
.panel h3 { font-size: 15px; color: #e0e6ed; margin: 0 0 16px; }
.arch-list { display: flex; flex-direction: column; gap: 10px; }
.arch-item { font-size: 13px; color: #a0aec0; line-height: 1.6; }
.arch-item strong { color: #63b3ed; }
</style>
