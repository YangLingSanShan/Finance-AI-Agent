<template>
  <div class="report-view">
    <header class="page-header"><h2>报告中心</h2><button @click="refresh" :disabled="loading">刷新</button></header>
    <form @submit.prevent="generateReport" class="report-form">
      <input v-model="stockCode" placeholder="六位股票代码，如 600519" pattern="[0-9]{6}" required maxlength="6" aria-label="股票代码" />
      <input v-model="query" placeholder="报告要求" required maxlength="4000" aria-label="报告要求" />
      <label><input type="checkbox" v-model="enableRag" />使用 RAG 知识库</label>
      <button class="btn-primary" :disabled="submitting">{{ submitting ? '提交中…' : '生成报告' }}</button>
    </form>
    <p class="hint">投研与风险分析完成后生成策略和报告。金融工具查询公开真实数据；报告将注明来源、日期及缺失项。</p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <div class="report-layout">
      <div class="report-list">
        <p v-if="!reports.length">暂无报告，请先生成。</p>
        <article v-for="report in reports" :key="report.id" class="report-card" :class="{ selected: selected?.id === report.id }">
          <button class="report-title" @click="openReport(report.id)">{{ report.title }}</button>
          <p>{{ labels[report.status] }} · {{ new Date(report.created_at).toLocaleString() }}</p>
          <p v-if="report.error" class="error">{{ report.error }}</p>
          <button :disabled="pending(report)" @click="remove(report)">删除</button>
          <button v-if="report.status === 'completed'" @click="download(report)">下载 Markdown</button>
        </article>
      </div>
      <article v-if="selected" class="report-detail">
        <h3>{{ selected.title }}</h3>
        <p>{{ labels[selected.status] }} · {{ selected.model }}</p>
        <p v-if="pending(selected)">正在生成，可稍后返回查看。</p>
        <p v-if="selected.error" class="error">{{ selected.error }}</p>
        <!-- Render generated Markdown as text: model-supplied HTML is never executed. -->
        <pre v-if="selected.content">{{ selected.content }}</pre>
        <details v-if="selected.sources?.length"><summary>来源证据</summary>
          <div v-for="(source, i) in selected.sources" :key="i"><strong>{{ source.citation || `来源${i + 1}` }}</strong><p>{{ source.label }}</p><p>{{ source.content }}</p><pre>{{ source.metadata }}</pre></div>
        </details>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { reportsApi, type Report } from '@/api/reports'
const route = useRoute()
const reports = ref<Report[]>([])
const selected = ref<Report | null>(null)
const stockCode = ref('')
const query = ref('分析基本面、风险和投资策略，生成完整报告')
const enableRag = ref(false)
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const labels = { pending: '等待生成', running: '生成中', completed: '已完成', failed: '生成失败' }
const pending = (r: Report) => r.status === 'pending' || r.status === 'running'
let timer: ReturnType<typeof setTimeout> | undefined
let active = true
let selectionVersion = 0
async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    reports.value = await reportsApi.list()
    const id = selected.value?.id
    const version = selectionVersion
    if (id) {
      if (!reports.value.some(r => r.id === id)) selected.value = null
      else {
        const detail = await reportsApi.get(id)
        if (version === selectionVersion) selected.value = detail
      }
    }
    error.value = ''
  } catch (e: any) { error.value = e.message }
  finally { loading.value = false }
}
async function openReport(id: string) {
  const version = ++selectionVersion
  try { const report = await reportsApi.get(id); if (version === selectionVersion) selected.value = report }
  catch (e: any) { error.value = e.message }
}
async function generateReport() {
  if (submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const report = await reportsApi.create(stockCode.value, query.value, enableRag.value)
    selectionVersion++
    selected.value = report
    await refresh()
  } catch (e: any) { error.value = e.message }
  finally { submitting.value = false }
}
async function remove(report: Report) {
  if (!window.confirm(`永久删除“${report.title}”？`)) return
  try {
    await reportsApi.delete(report.id)
    if (selected.value?.id === report.id) { selectionVersion++; selected.value = null }
    await refresh()
  } catch (e: any) { error.value = e.message }
}
async function download(report: Report) {
  try {
    const blob = await reportsApi.download(report.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = `report-${report.stock_code || report.id}.md`
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e: any) { error.value = e.message }
}
async function poll() {
  await refresh()
  if (active) timer = setTimeout(poll, 3000)
}
onMounted(async () => {
  await poll()
  if (typeof route.query.id === 'string') await openReport(route.query.id)
})
onUnmounted(() => { active = false; clearTimeout(timer) })
</script>

<style scoped>
.report-view { padding: 40px clamp(20px, 4vw, 64px); height: 100%; overflow-y: auto; color: var(--text); }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.report-form { display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0; }
input:not([type=checkbox]) { background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 10px; color: var(--text); flex: 1; min-width: 180px; }
button { background: var(--soft); color: var(--text); padding: 8px 12px; border: 0; border-radius: 6px; cursor: pointer; margin-right: 8px; }
button:disabled { opacity: .5; cursor: wait; }
.btn-primary { background: #262626; color: white; }
.report-layout { display: grid; grid-template-columns: minmax(250px, 1fr) 2fr; gap: 20px; }
.report-card, .report-detail { background: #fff; border: 1px solid var(--border); padding: 16px; border-radius: 8px; margin-bottom: 12px; min-width: 0; }
.selected { border-color: var(--text); }
.report-title { font-weight: 600; text-align: left; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.8; }
.error { color: #b44438; overflow-wrap: anywhere; }
.hint { color: var(--muted); font-size: 13px; }
@media(max-width: 900px) { .report-layout { grid-template-columns: 1fr; } }

@media(max-width: 1100px) { .stock-cards, .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media(max-width: 760px) { .page-header { padding-left: 40px; min-height: 36px; } .report-view, .knowledge-view, .dashboard-view, .llmops-view { padding: 18px; } }
@media(max-width: 420px) { .stock-cards, .metrics-grid { grid-template-columns: 1fr; } }
</style>
