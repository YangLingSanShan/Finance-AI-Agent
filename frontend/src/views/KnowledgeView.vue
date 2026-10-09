<template>
  <div class="knowledge-view">
    <header class="page-header"><h2>知识库管理</h2><button class="btn-primary" @click="openUpload()">上传文档</button></header>
    <p v-if="message" role="status">{{ message }}</p>
    <p>{{ documents.length }} 份文档 · {{ documents.reduce((n, d) => n + (d.status === 'indexed' ? d.chunk_count : 0), 0) }} 个已索引片段</p>
    <p v-if="loading">正在加载…</p><p v-else-if="!documents.length">暂无文档，请上传 PDF、TXT 或 Markdown。</p>
    <article v-for="doc in documents" :key="doc.id" class="document-card">
      <h3>{{ doc.title }}</h3><p>{{ doc.category }} · {{ doc.status }} · {{ doc.chunk_count }} 片段</p>
      <p>{{ doc.metadata.stock_code }} {{ doc.metadata.report_period }} {{ doc.metadata.disclosure_date }}</p>
      <p v-if="doc.error">索引失败，请检查服务配置后重新索引。</p>
      <button :disabled="busy" @click="openUpload(doc)">更新文件</button>
      <button :disabled="busy" @click="reindex(doc)">重新索引</button>
      <button :disabled="busy" @click="remove(doc)">删除</button>
    </article>
    <div v-if="showAddDialog" class="add-dialog"><form class="dialog-content" @submit.prevent="upload">
      <h3>{{ editing ? '更新文档' : '上传文档' }}</h3>
      <input class="dialog-input" v-model="title" placeholder="文档标题（默认文件名）" />
      <input class="dialog-input" v-model="category" placeholder="分类" required />
      <input class="dialog-input" v-model="stockCode" placeholder="证券代码（六位，可选）" pattern="[0-9]{6}" />
      <input class="dialog-input" v-model="reportPeriod" placeholder="报告期（如 2025 年度）" />
      <label>披露日期<input class="dialog-input" type="date" v-model="disclosureDate" /></label>
      <input class="dialog-input" v-model="sourceUrl" type="url" placeholder="来源链接 https://…" />
      <input type="file" accept=".pdf,.txt,.md" required @change="selectFile" />
      <p>最大 10 MB；扫描 PDF 请先 OCR。重复文件与元数据不会重复计数。</p>
      <p role="alert">{{ message }}</p>
      <div class="dialog-actions"><button type="button" :disabled="busy" @click="showAddDialog = false">取消</button><button class="btn-primary" :disabled="busy">{{ busy ? '正在索引…' : '上传并索引' }}</button></div>
    </form></div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ragApi, type KnowledgeDocument } from '../api/rag'
const documents = ref<KnowledgeDocument[]>([])
const loading = ref(false), busy = ref(false), showAddDialog = ref(false), message = ref('')
const title = ref(''), category = ref('general'), stockCode = ref(''), reportPeriod = ref(''), disclosureDate = ref(''), sourceUrl = ref(''), editing = ref('')
let file: File | undefined
async function refresh() { loading.value = true; try { documents.value = await ragApi.list() } catch (e) { message.value = String(e) } finally { loading.value = false } }
function openUpload(doc?: KnowledgeDocument) {
  editing.value = doc?.id || ''; title.value = doc?.title || ''; category.value = doc?.category || 'general'
  stockCode.value = doc?.metadata.stock_code || ''; reportPeriod.value = doc?.metadata.report_period || ''
  disclosureDate.value = doc?.metadata.disclosure_date || ''; sourceUrl.value = doc?.metadata.source_url || ''
  file = undefined; message.value = ''; showAddDialog.value = true
}
function selectFile(event: Event) { file = (event.target as HTMLInputElement).files?.[0] }
async function upload() {
  if (!file || file.size > 10 * 1024 * 1024 || !/\.(pdf|txt|md)$/i.test(file.name)) { message.value = '请选择不超过 10 MB 的 PDF、TXT 或 Markdown'; return }
  busy.value = true
  try {
    const data = new FormData(); data.append('file', file); data.append('title', title.value); data.append('category', category.value); data.append('doc_id', editing.value)
    data.append('metadata', JSON.stringify({ stock_code: stockCode.value, report_period: reportPeriod.value, disclosure_date: disclosureDate.value, source_url: sourceUrl.value }))
    const result = await ragApi.upload(data); message.value = result.deduplicated ? '文档已存在，未重复导入' : '索引完成'; showAddDialog.value = false; await refresh()
  } catch (e) { message.value = String(e); await refresh() } finally { busy.value = false }
}
async function remove(doc: KnowledgeDocument) {
  if (!window.confirm(`删除“${doc.title}”？删除后不再参与检索。`)) return
  busy.value = true; try { await ragApi.remove(doc.id); await refresh() } catch (e) { message.value = String(e) } finally { busy.value = false }
}
async function reindex(doc: KnowledgeDocument) {
  busy.value = true; try { await ragApi.reindex(doc.id); message.value = '重新索引完成'; await refresh() } catch (e) { message.value = String(e) } finally { busy.value = false }
}
onMounted(refresh)
</script>
<style scoped>
.document-card { padding: 20px 0; border-bottom: 1px solid var(--border); }
.document-card h3 { font-size: 15px; font-weight: 500; }
.document-card p { font-size: 12px; color: var(--muted); margin: 5px 0; }
.document-card button { margin: 8px 8px 0 0; }
.knowledge-view { padding: 40px clamp(20px, 4vw, 64px); height: 100%; overflow-y: auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 20px; color: var(--text); margin: 0; }
.btn-primary { padding: 8px 20px; background: #262626; border: none; border-radius: 8px; color: white; cursor: pointer; }
.stats-row { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-item { flex: 1; background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; }
.stat-value { font-size: 24px; font-weight: 700; color: var(--text); }
.stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
.category-section h3 { font-size: 15px; color: var(--text); margin: 0 0 16px; }
.category-chips { display: flex; flex-wrap: wrap; gap: 10px; }
.cat-chip { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: #fff; border: 1px solid var(--border); border-radius: 20px; font-size: 13px; color: #666660; }
.cat-count { background: var(--border); padding: 2px 8px; border-radius: 10px; font-size: 12px; color: var(--text); }
.add-dialog { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 100; }
.dialog-content { background: #fff; border: 1px solid var(--border); border-radius: 16px; padding: 24px; width: min(500px, calc(100vw - 32px)); max-height: 90dvh; overflow-y: auto; }
.dialog-content h3 { font-size: 18px; color: var(--text); margin: 0 0 16px; }
.dialog-input, .dialog-textarea { width: 100%; background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: var(--text); font-size: 14px; margin-bottom: 12px; box-sizing: border-box; font-family: inherit; }
.dialog-textarea { resize: vertical; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 12px; }
.btn-cancel { padding: 8px 20px; background: none; border: 1px solid var(--border); border-radius: 8px; color: #666660; cursor: pointer; }

@media(max-width: 1100px) { .stock-cards, .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media(max-width: 760px) { .page-header { padding-left: 40px; min-height: 36px; } .report-view, .knowledge-view, .dashboard-view, .llmops-view { padding: 18px; } }
@media(max-width: 420px) { .stock-cards, .metrics-grid { grid-template-columns: 1fr; } }
</style>
