<template>
  <div class="chat-view">
    <header class="chat-header">
      <div class="header-left">
        <h2>💬 智能投研对话</h2>
        <span class="model-tag">Qwen-Plus + RAG</span>
      </div>
      <div class="header-right">
        <button class="btn-icon" @click="clearChat" title="清空对话">🗑</button>
      </div>
    </header>

    <div class="chat-body" ref="chatBodyRef">
      <div v-if="messages.length === 0" class="welcome-panel">
        <div class="welcome-icon">🤖</div>
        <h3>金融分析 AI Agent</h3>
        <p>基于 LLM + Agent + RAG 的智能投研助手</p>
        <div class="quick-prompts">
          <div class="prompt-label">试试这样问我：</div>
          <button class="prompt-chip" @click="quickAsk('分析贵州茅台600519的基本面和估值')">
            📈 分析贵州茅台的基本面
          </button>
          <button class="prompt-chip" @click="quickAsk('对宁德时代进行⻛险评估')">
            ⚠ 评估宁德时代的⻛险
          </button>
          <button class="prompt-chip" @click="quickAsk('分析当前市场行情，给出投资建议')">
            💡 分析市场并给出投资建议
          </button>
        </div>
      </div>

      <div v-else class="message-list">
        <div v-for="(msg, idx) in messages" :key="idx" class="message-item" :class="msg.role">
          <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="message-content">
            <div class="message-header">
              <span class="sender-name">{{ msg.role === 'user' ? '你' : 'AI Agent' }}</span>
              <span v-if="msg.agent_type" class="agent-badge">{{ msg.agent_type }}</span>
            </div>
            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
            <div v-if="msg.sources && msg.sources.length > 0" class="sources-panel">
              <div class="sources-title">📚 参考来源</div>
              <div v-for="(src, sidx) in msg.sources" :key="sidx" class="source-item">
                <span class="source-score">{{ (src.score * 100).toFixed(0) }}%</span>
                <span class="source-content">{{ src.content }}</span>
              </div>
            </div>
            <div v-if="msg.token_usage || msg.latency_ms" class="message-meta">
              <span v-if="msg.token_usage">💎 {{ msg.token_usage.total }} tokens</span>
              <span v-if="msg.latency_ms">⏱ {{ msg.latency_ms }}ms</span>
            </div>
          </div>
        </div>

        <div v-if="isLoading" class="message-item assistant">
          <div class="message-avatar">🤖</div>
          <div class="message-content">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-footer">
      <div class="input-toolbar">
        <label class="toolbar-item">
          <input type="checkbox" v-model="enableRAG" />
          <span>启用RAG增强</span>
        </label>
      </div>
      <div class="input-row">
        <textarea v-model="inputMessage" class="input-area" placeholder="输入你的金融分析问题..."
          rows="1" @keydown.enter.exact.prevent="sendMessage" @input="autoResize" ref="inputRef"></textarea>
        <button class="send-btn" @click="sendMessage" :disabled="!inputMessage.trim() || isLoading">
          {{ isLoading ? '⏳' : '🚀' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { marked } from 'marked'
import { chatApi, ChatMessage } from '@/api/chat'

const messages = ref<Array<ChatMessage & { sources?: any[]; token_usage?: any; latency_ms?: number }>>([])
const inputMessage = ref('')
const isLoading = ref(false)
const enableRAG = ref(true)
const sessionId = ref(`session_${Date.now()}`)
const chatBodyRef = ref<HTMLElement>()
const inputRef = ref<HTMLTextAreaElement>()

function renderMarkdown(text: string) {
  return marked.parse(text, { async: false }) as string
}

function autoResize() {
  const el = inputRef.value
  if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 200) + 'px' }
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text || isLoading.value) return

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
    messages.value.push({
      role: 'assistant', content: res.message,
      agent_type: res.agent_type, sources: res.sources,
      token_usage: res.token_usage, latency_ms: res.latency_ms,
    })
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: `❌ 出错了：${e.message}` })
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function quickAsk(question: string) { inputMessage.value = question; sendMessage() }
function clearChat() { messages.value = []; sessionId.value = `session_${Date.now()}` }
function scrollToBottom() {
  if (chatBodyRef.value) chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}
</script>

<style scoped>
.chat-view { display: flex; flex-direction: column; height: 100%; background: #0a0e1a; }
.chat-header { display: flex; align-items: center; justify-content: space-between;
  padding: 16px 24px; border-bottom: 1px solid rgba(99,179,237,0.15);
  background: linear-gradient(90deg, rgba(99,179,237,0.08) 0%, transparent 100%); }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-left h2 { font-size: 18px; font-weight: 600; color: #e0e6ed; margin: 0; }
.model-tag { padding: 4px 10px; background: rgba(99,179,237,0.2); border-radius: 20px; font-size: 12px; color: #63b3ed; }
.btn-icon { background: none; border: none; cursor: pointer; font-size: 18px; padding: 8px; border-radius: 8px; }
.btn-icon:hover { background: rgba(99,179,237,0.15); }
.chat-body { flex: 1; overflow-y: auto; padding: 24px; }
.welcome-panel { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; color: #a0aec0; }
.welcome-icon { font-size: 64px; margin-bottom: 16px; }
.welcome-panel h3 { font-size: 24px; color: #e0e6ed; margin: 0 0 8px; }
.welcome-panel p { font-size: 14px; color: #718096; margin: 0 0 32px; }
.quick-prompts { display: flex; flex-direction: column; gap: 12px; align-items: center; }
.prompt-label { font-size: 13px; color: #718096; }
.prompt-chip { padding: 10px 20px; background: rgba(99,179,237,0.1); border: 1px solid rgba(99,179,237,0.25);
  border-radius: 24px; color: #a0aec0; cursor: pointer; font-size: 13px; transition: all 0.2s; max-width: 400px; }
.prompt-chip:hover { background: rgba(99,179,237,0.2); border-color: rgba(99,179,237,0.5); color: #63b3ed; transform: translateY(-2px); }
.message-list { display: flex; flex-direction: column; gap: 20px; }
.message-item { display: flex; gap: 12px; max-width: 80%; }
.message-item.user { align-self: flex-end; flex-direction: row-reverse; }
.message-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; background: rgba(99,179,237,0.15); }
.message-item.assistant .message-avatar { background: rgba(104,211,145,0.15); }
.message-content { flex: 1; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px 18px; }
.message-item.user .message-content { background: rgba(99,179,237,0.12); border-color: rgba(99,179,237,0.25); }
.message-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.sender-name { font-size: 13px; font-weight: 600; color: #a0aec0; }
.agent-badge { padding: 2px 8px; background: rgba(104,211,145,0.2); border-radius: 10px; font-size: 11px; color: #68d391; }
.message-text { font-size: 14px; line-height: 1.7; color: #e0e6ed; word-break: break-word; }
.message-text :deep(strong) { color: #63b3ed; }
.message-text :deep(pre) { background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; overflow-x: auto; }
.message-text :deep(table) { width: 100%; border-collapse: collapse; margin: 8px 0; }
.message-text :deep(th), .message-text :deep(td) { padding: 8px 12px; border: 1px solid rgba(255,255,255,0.1); font-size: 13px; }
.message-text :deep(th) { background: rgba(99,179,237,0.1); color: #63b3ed; }
.sources-panel { margin-top: 12px; padding: 10px; background: rgba(99,179,237,0.08); border-radius: 8px; border: 1px solid rgba(99,179,237,0.15); }
.sources-title { font-size: 12px; color: #63b3ed; margin-bottom: 8px; font-weight: 600; }
.source-item { display: flex; align-items: flex-start; gap: 8px; padding: 4px 0; font-size: 12px; color: #718096; }
.source-score { color: #68d391; font-weight: 600; flex-shrink: 0; }
.message-meta { display: flex; gap: 12px; margin-top: 8px; font-size: 12px; color: #718096; }
.typing-indicator { display: flex; gap: 4px; padding: 4px 0; }
.typing-indicator span { width: 8px; height: 8px; border-radius: 50%; background: #63b3ed; animation: bounce 1.4s infinite ease-in-out; }
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }
.chat-footer { border-top: 1px solid rgba(99,179,237,0.15); padding: 16px 24px; background: rgba(15,22,41,0.8); }
.input-toolbar { display: flex; gap: 16px; margin-bottom: 10px; }
.toolbar-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #718096; cursor: pointer; }
.toolbar-item input[type="checkbox"] { accent-color: #63b3ed; }
.input-row { display: flex; gap: 12px; align-items: flex-end; }
.input-area { flex: 1; background: rgba(255,255,255,0.06); border: 1px solid rgba(99,179,237,0.2);
  border-radius: 12px; padding: 12px 16px; color: #e0e6ed; font-size: 14px; resize: none; outline: none;
  font-family: inherit; line-height: 1.5; transition: border-color 0.2s; }
.input-area:focus { border-color: rgba(99,179,237,0.5); background: rgba(99,179,237,0.06); }
.input-area::placeholder { color: #4a5568; }
.send-btn { width: 44px; height: 44px; border-radius: 12px; border: none;
  background: linear-gradient(135deg, #3182ce, #63b3ed); color: white; font-size: 18px;
  cursor: pointer; transition: all 0.2s; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.send-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(99,179,237,0.4); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
