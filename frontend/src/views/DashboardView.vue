<template>
  <div class="dashboard-view">
    <header class="page-header"><h2>金融数据看板</h2></header>
    <p class="hint">腾讯证券公开行情，可能延迟；以各卡片的行情时间为准。成交量单位为手。</p>
    <button :disabled="loading" @click="load">{{ loading ? '查询中…' : '刷新行情' }}</button>
    <p v-if="errors.length" role="alert">{{ errors.join('；') }}</p>
    <div class="stock-cards">
      <div v-for="quote in quotes" :key="quote.data.symbol" class="stock-card">
        <div class="stock-top">
          <div class="stock-name">{{ quote.data.name }}</div>
          <div class="stock-code">{{ quote.data.code }}</div>
        </div>
        <div class="stock-price">{{ quote.data.price.toFixed(2) }} {{ quote.data.isIndex ? '点' : '元' }}</div>
        <div class="stock-change" :class="(quote.data.change_pct ?? 0) >= 0 ? 'up' : 'down'">
          {{ quote.data.change_pct == null ? '涨跌幅缺失' : quote.data.change_pct.toFixed(2) + '%' }}
        </div>
        <div class="stock-vol">成交量：{{ quote.data.volume?.toLocaleString() ?? '缺失' }} 手</div>
        <div class="stock-vol">行情时间：{{ quote.as_of }}</div>
        <a :href="quote.source_url" target="_blank" rel="noopener noreferrer">{{ quote.source }}</a>
        <p v-for="warning in quote.warnings" :key="warning" class="stock-vol">{{ warning }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api'

type Quote = {
  data: { code: string; symbol: string; name: string; price: number; change_pct: number | null;
    volume: number | null; isIndex?: boolean };
  as_of: string; source: string; source_url: string; warnings: string[]
}
const quotes = ref<Quote[]>([])
const errors = ref<string[]>([])
const loading = ref(false)
async function load() {
  loading.value = true
  quotes.value = []
  errors.value = []
  const codes = ['600519', '000858', '300750', '601318']
  const results = await Promise.allSettled([
    api.get<unknown, { indices: Quote[]; missing: string[] }>('/data/market'),
    ...codes.map(code => api.get<unknown, Quote>(`/data/stock/${code}/quote`)),
  ])
  results.forEach((result, index) => {
    if (result.status === 'rejected') {
      errors.value.push(`${index === 0 ? '市场指数' : codes[index - 1]}：${result.reason.message}`)
    } else if ('indices' in result.value) {
      quotes.value.push(...result.value.indices.map(q => ({ ...q, data: { ...q.data, isIndex: true } })))
      if (result.value.missing.length) errors.value.push(`缺失指数：${result.value.missing.join('、')}`)
    } else {
      quotes.value.push(result.value)
    }
  })
  loading.value = false
}
onMounted(load)
</script>

<style scoped>
.dashboard-view { padding: 40px clamp(20px, 4vw, 64px); height: 100%; overflow-y: auto; }
.page-header h2 { font-size: 20px; font-weight: 600; color: var(--text); margin: 0 0 24px; }
.stock-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stock-card { background: linear-gradient(135deg, var(--soft), #fff); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.stock-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.stock-name { font-size: 15px; font-weight: 600; color: var(--text); }
.stock-code { font-size: 12px; color: var(--muted); }
.stock-price { font-size: 24px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
.stock-change { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.stock-change.up { color: #b44438; }
.stock-change.down { color: #348263; }
.stock-vol { font-size: 12px; color: var(--muted); }
.panel { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.panel h3 { font-size: 15px; color: var(--text); margin: 0 0 16px; }
.arch-list { display: flex; flex-direction: column; gap: 10px; }
.arch-item { font-size: 13px; color: #666660; line-height: 1.6; }
.arch-item strong { color: var(--text); }

@media(max-width: 1100px) { .stock-cards, .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media(max-width: 760px) { .page-header { padding-left: 40px; min-height: 36px; } .report-view, .knowledge-view, .dashboard-view, .llmops-view { padding: 18px; } }
@media(max-width: 420px) { .stock-cards, .metrics-grid { grid-template-columns: 1fr; } }
</style>
