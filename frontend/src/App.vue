<template>
  <div id="app" class="app-container">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="logo">🤖 金融AI Agent</h1>
        <p class="subtitle">LLM + Agent + RAG</p>
      </div>
      <nav class="nav-menu">
        <router-link to="/" class="nav-item" active-class="active">
          <span class="nav-icon">💬</span>智能对话
        </router-link>
        <router-link to="/dashboard" class="nav-item" active-class="active">
          <span class="nav-icon">📊</span>数据看板
        </router-link>
        <router-link to="/report" class="nav-item" active-class="active">
          <span class="nav-icon">📝</span>报告中心
        </router-link>
        <router-link to="/knowledge" class="nav-item" active-class="active">
          <span class="nav-icon">📚</span>知识库
        </router-link>
        <router-link to="/llmops" class="nav-item" active-class="active">
          <span class="nav-icon">⚙</span>LLMOps监控
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <div class="status-indicator">
          <span class="status-dot"></span>系统正常
        </div>
      </div>
    </aside>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-container { display: flex; height: 100vh; background: #0a0e1a; color: #e0e6ed; }
.sidebar { width: 240px; background: linear-gradient(180deg, #0f1629 0%, #1a1f35 100%);
  border-right: 1px solid rgba(99,179,237,0.15); display: flex; flex-direction: column; padding: 20px 0; }
.sidebar-header { padding: 0 20px 20px; border-bottom: 1px solid rgba(99,179,237,0.1); }
.logo { font-size: 18px; font-weight: 700; color: #63b3ed; margin: 0; }
.subtitle { font-size: 11px; color: #718096; margin: 4px 0 0; }
.nav-menu { flex: 1; padding: 16px 0; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 12px 20px;
  color: #a0aec0; text-decoration: none; font-size: 14px; transition: all 0.2s;
  border-left: 3px solid transparent; }
.nav-item:hover { background: rgba(99,179,237,0.1); color: #63b3ed; }
.nav-item.active { background: rgba(99,179,237,0.15); color: #63b3ed; border-left-color: #63b3ed; }
.sidebar-footer { padding: 16px 20px; border-top: 1px solid rgba(99,179,237,0.1); }
.status-indicator { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #68d391; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #68d391; box-shadow: 0 0 8px #68d391; }
.main-content { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
</style>
