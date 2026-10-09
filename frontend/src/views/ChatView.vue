<template>
  <div class="chat-layout">
    <Teleport to="#conversation-sidebar"><aside class="history-panel" aria-label="历史对话">
      <button class="history-new" :disabled="isLoading" @click="newConversation">＋ 新建对话</button>
      <div class="history-tabs">
        <button :class="{ selected: !showArchived }" :disabled="isLoading" @click="changeFilter(false)">历史对话</button>
        <button :class="{ selected: showArchived }" :disabled="isLoading" @click="changeFilter(true)">已归档</button>
      </div>
      <p v-if="!conversations.length" class="history-empty">{{ showArchived ? '暂无归档对话' : '暂无历史对话' }}</p>
      <div class="history-list">
        <div v-for="item in conversations" :key="item.id" class="history-item" :class="{ selected: sessionId === item.id }">
          <button class="history-title" :disabled="isLoading" @click="openConversation(item.id)" :title="item.title">
            {{ item.title }}
            <small>{{ new Date(item.updated_at).toLocaleString() }}</small>
          </button>
          <div class="history-actions">
            <button :disabled="isLoading" @click="archiveConversation(item)">{{ item.archived ? '恢复' : '归档' }}</button>
            <button :disabled="isLoading" @click="deleteConversation(item)">删除</button>
          </div>
        </div>
      </div>
    </aside></Teleport>
  <div class="chat-view">
    <header class="chat-header">
      <div class="header-left">
        <h2>{{ currentTitle }}</h2>
        <span class="model-tag">{{ modelName }}{{ enableRAG ? " + RAG" : "" }}</span>
      </div>
    </header>

    <p v-if="notice" role="alert" class="chat-notice">{{ notice }}</p>
    <div class="chat-body" ref="chatBodyRef">
      <div v-if="messages.length === 0" class="welcome-panel">
        <div class="welcome-eyebrow">FINANCIAL INTELLIGENCE</div>
        <h3>今天，想了解什么？</h3>
        <p>从一个问题开始，探索公司、市场与投资逻辑。</p>
        <div class="quick-prompts">
          <div class="prompt-label">从这里开始</div>
          <button class="prompt-chip" @click="quickAsk('分析贵州茅台600519的基本面和估值')">
            分析贵州茅台的基本面 ↗
          </button>
          <button class="prompt-chip" @click="quickAsk('对宁德时代进行⻛险评估')">
            评估宁德时代的风险 ↗
          </button>
          <button class="prompt-chip" @click="quickAsk('分析当前市场行情，给出投资建议')">
            了解当前市场与投资机会 ↗
          </button>
        </div>
      </div>

      <div v-else class="message-list">
        <div v-for="(msg, idx) in messages" :key="idx" class="message-item" :class="msg.role">
          <div class="message-avatar">{{ msg.role === 'user' ? '你' : 'F' }}</div>
          <div class="message-content">
            <div class="message-header">
              <span class="sender-name">{{ msg.role === 'user' ? '你' : 'AI Agent' }}</span>
              <span v-if="msg.agent_type" class="agent-badge">{{ msg.agent_type }}</span>
            </div>
            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
            <router-link v-if="msg.report_id" :to="{ path: '/report', query: { id: msg.report_id } }">在报告中心查看与下载</router-link>
            <details v-if="msg.tool_calls?.length">
              <summary>工具调用 {{ msg.tool_calls.length }} 次</summary>
              <div v-for="(call, index) in msg.tool_calls" :key="index">
                <strong>{{ call.name }}：{{ call.success ? '成功' : '失败' }}</strong>
                <pre>{{ call.error || call.result }}</pre>
              </div>
            </details>
            <div v-if="msg.sources && msg.sources.length > 0" class="sources-panel">
              <div class="sources-title">参考来源</div>
              <div v-for="(src, sidx) in msg.sources" :key="sidx" class="source-item">
                <span class="source-score">{{ src.citation || `来源${sidx + 1}` }}</span>
                <span class="source-content">{{ src.label }}<br />{{ src.content }}</span>
              </div>
            </div>
            <div v-if="msg.token_usage || msg.latency_ms" class="message-meta">
              <span v-if="msg.token_usage">{{ msg.token_usage.total }} tokens</span>
              <span v-if="msg.latency_ms">{{ msg.latency_ms }}ms</span>
            </div>
          </div>
        </div>

        <div v-if="isLoading" class="message-item assistant">
          <div class="message-avatar">F</div>
          <div class="message-content">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="currentArchived" class="chat-notice">
      此对话已归档，恢复后可以继续提问。
      <button :disabled="isLoading" @click="restoreCurrent">恢复对话</button>
    </div>
    <div v-else class="chat-footer">
      <div class="input-toolbar">
        <label class="toolbar-item">
          <input type="checkbox" v-model="enableRAG" />
          <span>检索知识库</span>
        </label>
      </div>
      <div class="input-row">
        <textarea v-model="inputMessage" class="input-area" placeholder="向 FinSight 提问…"
          rows="1" :disabled="isLoading" @keydown.enter.exact.prevent="sendMessage" @input="autoResize" ref="inputRef"></textarea>
        <button aria-label="发送消息" class="send-btn" @click="sendMessage" :disabled="!inputMessage.trim() || isLoading">
          {{ isLoading ? '···' : '↑' }}
        </button>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { chatApi, ChatMessage } from '@/api/chat'
import { conversationsApi, type Conversation } from '@/api/conversations'

const messages = ref<Array<ChatMessage & { sources?: any[]; token_usage?: any; latency_ms?: number }>>([])
const inputMessage = ref('')
const isLoading = ref(false)
const enableRAG = ref(true)
const modelName = ref('已配置模型')
const sessionId = ref('')
const currentTitle = ref('智能投研对话')
const currentArchived = ref(false)
const conversations = ref<Conversation[]>([])
const showArchived = ref(false)
const notice = ref('')
const chatBodyRef = ref<HTMLElement>()
const inputRef = ref<HTMLTextAreaElement>()

function autoResize() {
  const el = inputRef.value
  if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 200) + 'px' }
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text || isLoading.value || currentArchived.value) return

  isLoading.value = true
  notice.value = ''
  try {
    if (!sessionId.value) selectEmpty(await conversationsApi.create())
  } catch (e: any) {
    notice.value = `创建失败：${e.message}`
    isLoading.value = false
    return
  }
  messages.value.push({ role: 'user', content: text })
  inputMessage.value = ''
  isLoading.value = true
  await nextTick()
  scrollToBottom()

  try {
    const res = await chatApi.send({
      session_id: sessionId.value,
      message: text,
      enable_rag: enableRAG.value,
      stream: false,
    })
    localStorage.setItem('financial-active-conversation', res.session_id)
    modelName.value = res.model
    sessionId.value = res.session_id
    messages.value.push({
      role: 'assistant', content: res.message, tool_calls: res.tool_calls, report_id: res.report_id,
      agent_type: res.agent_type, sources: res.sources,
      token_usage: res.token_usage, latency_ms: res.latency_ms,
    })
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: `❌ 出错了：${e.message}` })
  } finally {
    try {
      await refreshList()
      currentTitle.value = conversations.value.find(item => item.id === sessionId.value)?.title || currentTitle.value
    } catch (e: any) { notice.value = `历史列表更新失败：${e.message}` }
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function quickAsk(question: string) { inputMessage.value = question; sendMessage() }
async function refreshList() {
  conversations.value = await conversationsApi.list(showArchived.value)
}
function selectEmpty(item?: Conversation) {
  sessionId.value = item?.id || ''
  currentTitle.value = item?.title || '智能投研对话'
  currentArchived.value = item?.archived || false
  messages.value = []
  inputMessage.value = ''
  localStorage.setItem('financial-active-conversation', sessionId.value)
}
async function loadConversation(id: string) {
  const item = await conversationsApi.get(id)
  selectEmpty(item)
  messages.value = item.messages
  modelName.value = [...item.messages].reverse().find(msg => msg.model)?.model || '已配置模型'
  await nextTick()
  scrollToBottom()
}
async function action(work: () => Promise<void>) {
  if (isLoading.value) return
  isLoading.value = true
  notice.value = ''
  try { await work() } catch (e: any) { notice.value = e.message }
  finally { isLoading.value = false }
}
async function newConversation() {
  await action(async () => {
    const item = await conversationsApi.create()
    showArchived.value = false
    selectEmpty(item)
    await refreshList()
  })
}
async function openConversation(id: string) { await action(() => loadConversation(id)) }
async function changeFilter(archived: boolean) {
  await action(async () => {
    const items = await conversationsApi.list(archived)
    showArchived.value = archived
    conversations.value = items
  })
}
async function archiveConversation(item: Conversation) {
  await action(async () => {
    const updated = await conversationsApi.archive(item.id, !item.archived)
    if (sessionId.value === item.id) currentArchived.value = updated.archived
    await refreshList()
  })
}
async function restoreCurrent() {
  await archiveConversation({ id: sessionId.value, archived: true } as Conversation)
  await changeFilter(false)
}
async function deleteConversation(item: Conversation) {
  if (isLoading.value || !window.confirm(`永久删除“${item.title}”？此操作无法撤销。`)) return
  await action(async () => {
    await conversationsApi.delete(item.id)
    if (sessionId.value === item.id) selectEmpty()
    await refreshList()
  })
}
onMounted(() => action(async () => {
  await refreshList()
  const lastId = localStorage.getItem('financial-active-conversation')
  if (lastId) {
    try {
      await loadConversation(lastId)
      showArchived.value = currentArchived.value
      await refreshList()
    } catch (e: any) {
      selectEmpty()
      notice.value = `上次对话无法恢复：${e.message}`
    }
  }
}))
function scrollToBottom() {
  if (chatBodyRef.value) chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}
</script>

<style scoped>
.chat-layout, .chat-view { height: 100%; min-width: 0; }
.chat-view { display: flex; flex-direction: column; }
.history-panel { display: flex; flex-direction: column; min-height: 0; font-size: 13px; }
.history-panel button { border: 0; background: transparent; }
.history-new { text-align: left; padding: 10px 12px; border: 1px solid var(--border) !important; background: white !important; border-radius: 9px; }
.history-tabs { display: flex; gap: 12px; margin: 18px 0 10px; }
.history-tabs button { font-size: 11px; color: var(--muted); padding: 3px 8px; }
.history-tabs .selected { color: var(--text); font-weight: 600; }
.history-list { overflow-y: auto; min-height: 0; }
.history-item { padding: 7px 10px; border-radius: 8px; margin-bottom: 4px; }
.history-item:hover, .history-item.selected { background: var(--hover); }
.history-title { width: 100%; text-align: left; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; padding: 0; }
.history-title small { display: block; font-size: 10px; color: var(--muted); margin-top: 3px; }
.history-actions { display: flex; gap: 8px; }
.history-actions button { font-size: 10px; color: var(--muted); padding: 4px 0 0; }
.history-empty { color: var(--muted); padding: 8px 12px; font-size: 12px; }
.chat-header { padding: 22px 32px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-left h2 { font-size: 16px; font-weight: 500; max-width: 45vw; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
.model-tag { color: var(--muted); font-size: 11px; background: var(--soft); border-radius: 6px; padding: 3px 8px; }
.chat-body { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 32px; }
.welcome-panel { min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; padding-bottom: 60px; text-align: center; }
.welcome-eyebrow { color: var(--muted); font-size: 10px; letter-spacing: 2.4px; margin-bottom: 22px; }
.welcome-panel h3 { font-size: clamp(25px, 3vw, 36px); letter-spacing: -1px; font-weight: 500; margin-bottom: 14px; }
.welcome-panel p { font-size: 14px; color: var(--muted); }
.quick-prompts { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 36px; max-width: 650px; }
.prompt-label { width: 100%; font-size: 11px; color: #94948e; margin-bottom: 4px; }
.prompt-chip { background: white; border-radius: 12px; padding: 13px 16px; color: #5f5f5a; font-size: 12px; }
.message-list { width: 100%; max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: 32px; padding: 20px 0 30px; }
.message-item { display: flex; gap: 14px; min-width: 0; }
.message-item.user { align-self: flex-end; max-width: 85%; }
.message-avatar { width: 28px; height: 28px; flex-shrink: 0; border-radius: 50%; background: var(--soft); display: grid; place-items: center; font-family: Georgia, serif; }
.user .message-avatar, .user .message-header { display: none; }
.message-content { min-width: 0; flex: 1; }
.user .message-content { background: #f1f1ef; padding: 12px 20px; border-radius: 22px; }
.message-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 12px; }
.sender-name { font-weight: 600; }
.agent-badge { font-size: 10px; color: var(--muted); padding: 1px 7px; background: var(--soft); border-radius: 4px; }
.message-text { font-size: 15px; line-height: 1.85; overflow-wrap: anywhere; }
.message-text :deep(p + p) { margin-top: 14px; }
.message-text :deep(ul), .message-text :deep(ol) { padding-left: 24px; margin: 12px 0; }
.message-text :deep(pre) { background: var(--soft); padding: 16px; border-radius: 12px; overflow: auto; margin: 14px 0; }
.message-text :deep(table) { display: block; overflow: auto; border-collapse: collapse; margin: 16px 0; }
.message-text :deep(th), .message-text :deep(td) { padding: 9px 14px; border: 1px solid var(--border); font-size: 13px; }
.message-text :deep(th) { background: var(--soft); }
.sources-panel { margin-top: 20px; border: 1px solid var(--border); padding: 14px; border-radius: 12px; }
.sources-title { font-size: 12px; font-weight: 600; margin-bottom: 8px; }
.source-item { display: flex; gap: 10px; font-size: 12px; color: var(--muted); padding: 6px 0; overflow-wrap: anywhere; }
.source-score { flex-shrink: 0; color: var(--text); }
.message-meta { display: flex; gap: 12px; font-size: 10px; color: var(--muted); margin-top: 14px; }
.chat-footer { width: calc(100% - 64px); max-width: 760px; margin: 0 auto 28px; padding: 14px 16px; background: #f5f5f3; border: 1px solid #eaeae7; border-radius: 24px; box-shadow: 0 3px 14px #00000004; }
.input-toolbar { margin-bottom: 8px; }
.toolbar-item { display: inline-flex; align-items: center; gap: 7px; font-size: 11px; color: var(--muted); cursor: pointer; }
.input-row { display: flex; gap: 12px; align-items: flex-end; }
.input-area { width: 100%; flex: 1; border: 0; background: transparent; padding: 8px 2px; font-size: 15px; resize: none; line-height: 1.6; max-height: 200px; }
.input-area:focus { outline: none; }
.send-btn { width: 36px; height: 36px; padding: 0; border: 0; border-radius: 50%; background: #262626; color: white; font-size: 23px; flex-shrink: 0; }
.send-btn:hover:not(:disabled) { background: #444; }
.chat-notice { padding: 10px 24px; background: #faf5e9; color: #846630; font-size: 12px; }
.typing-indicator { display: flex; gap: 5px; padding: 12px 0; }
.typing-indicator span { height: 6px; width: 6px; background: #999; border-radius: 50%; animation: pulse 1s infinite alternate; }
.typing-indicator span:nth-child(2) { animation-delay: .2s; }
.typing-indicator span:nth-child(3) { animation-delay: .4s; }
@keyframes pulse { to { opacity: .25; } }
@media(max-width: 760px) { .chat-header { padding: 22px 16px 18px 60px; } .header-left { flex-wrap: wrap; gap: 4px; } .model-tag { font-size: 10px; } .chat-body { padding: 12px 18px; } .chat-footer { width: calc(100% - 28px); margin-bottom: 16px; } .welcome-panel { padding-bottom: 20px; } .quick-prompts { margin-top: 24px; } .welcome-panel p { font-size: 12px; } }
</style>
