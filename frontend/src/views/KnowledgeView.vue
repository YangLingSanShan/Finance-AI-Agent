<template>
  <div class="knowledge-view">
    <header class="page-header">
      <h2>📚 知识库管理</h2>
      <button class="btn-primary" @click="showAddDialog = true">+ 上传文档</button>
    </header>
    <div class="stats-row">
      <div class="stat-item"><div class="stat-value">{{ totalChunks }}</div><div class="stat-label">知识片段数</div></div>
      <div class="stat-item"><div class="stat-value">ChromaDB</div><div class="stat-label">向量引擎</div></div>
      <div class="stat-item"><div class="stat-value">cosine</div><div class="stat-label">相似度算法</div></div>
    </div>
    <div class="category-section">
      <h3>📂 知识分类</h3>
      <div class="category-chips">
        <div v-for="cat in categories" :key="cat.name" class="cat-chip">
          <span>{{ cat.name }}</span>
          <span class="cat-count">{{ cat.count }}</span>
        </div>
      </div>
    </div>
    <div class="add-dialog" v-if="showAddDialog">
      <div class="dialog-content">
        <h3>添加知识</h3>
        <input v-model="newTitle" placeholder="标题" class="dialog-input" />
        <textarea v-model="newContent" placeholder="输入知识内容..." class="dialog-textarea" rows="6"></textarea>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="showAddDialog = false">取消</button>
          <button class="btn-primary" @click="addKnowledge">确认添加</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
const totalChunks = ref(2847)
const showAddDialog = ref(false)
const newTitle = ref('')
const newContent = ref('')
const categories = ref([
  { name: '📰 财经新闻', count: 856 },
  { name: '📋 年报半年报', count: 1203 },
  { name: '📖 券商研报', count: 412 },
  { name: '⚖ 金融法规', count: 156 },
  { name: '📌 内部知识', count: 220 },
])
function addKnowledge() { showAddDialog.value = false; newTitle.value = ''; newContent.value = '' }
</script>

<style scoped>
.knowledge-view { padding: 24px; height: 100%; overflow-y: auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 20px; color: #e0e6ed; margin: 0; }
.btn-primary { padding: 8px 20px; background: #3182ce; border: none; border-radius: 8px; color: white; cursor: pointer; }
.stats-row { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-item { flex: 1; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 20px; text-align: center; }
.stat-value { font-size: 24px; font-weight: 700; color: #63b3ed; }
.stat-label { font-size: 12px; color: #718096; margin-top: 4px; }
.category-section h3 { font-size: 15px; color: #e0e6ed; margin: 0 0 16px; }
.category-chips { display: flex; flex-wrap: wrap; gap: 10px; }
.cat-chip { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; font-size: 13px; color: #a0aec0; }
.cat-count { background: rgba(99,179,237,0.2); padding: 2px 8px; border-radius: 10px; font-size: 12px; color: #63b3ed; }
.add-dialog { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 100; }
.dialog-content { background: #1a1f35; border: 1px solid rgba(99,179,237,0.3); border-radius: 16px; padding: 24px; width: 500px; }
.dialog-content h3 { font-size: 18px; color: #e0e6ed; margin: 0 0 16px; }
.dialog-input, .dialog-textarea { width: 100%; background: rgba(255,255,255,0.06); border: 1px solid rgba(99,179,237,0.2); border-radius: 8px; padding: 10px 14px; color: #e0e6ed; font-size: 14px; margin-bottom: 12px; box-sizing: border-box; font-family: inherit; }
.dialog-textarea { resize: vertical; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 12px; }
.btn-cancel { padding: 8px 20px; background: none; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; color: #a0aec0; cursor: pointer; }
</style>
