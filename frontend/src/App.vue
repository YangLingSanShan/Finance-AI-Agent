<template>
  <div class="app-container">
    <button v-if="sidebarOpen" class="sidebar-backdrop" aria-label="关闭导航" @click="sidebarOpen = false"></button>
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <router-link to="/" class="brand"><span class="brand-mark">F</span><span>FinSight<small>金融研究助手</small></span></router-link>
      <nav class="nav-menu" aria-label="主导航">
        <router-link v-for="item in navigation" :key="item.path" :to="item.path" class="nav-item" exact-active-class="active" @click="sidebarOpen = false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="item.icon" /></svg>{{ item.label }}
        </router-link>
      </nav>
      <div id="conversation-sidebar" class="conversation-slot"></div>
      <div class="sidebar-footer"><span class="workspace-avatar">F</span><div>个人工作空间<small>金融分析 · 知识与洞察</small></div></div>
    </aside>
    <main class="main-content">
      <button class="mobile-menu" @click="sidebarOpen = !sidebarOpen" :aria-expanded="sidebarOpen" aria-label="展开导航">☰</button>
      <router-view />
    </main>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
const sidebarOpen = ref(false)
const navigation = [
  { path: '/', label: '智能对话', icon: 'M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5A8.5 8.5 0 0 1 10.5 3h2A8.5 8.5 0 0 1 21 11.5Z M7 9h9M7 13h6' },
  { path: '/dashboard', label: '数据看板', icon: 'M4 4v16h16M8 16v-5M13 16V7M18 16v-8' },
  { path: '/report', label: '报告中心', icon: 'M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h6' },
  { path: '/knowledge', label: '知识库', icon: 'M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3V4Zm9 2v15' },
  { path: '/llmops', label: '运行监控', icon: 'M3 12h4l3-8 4 16 3-8h4' },
]
</script>
<style scoped>
.app-container { display: flex; height: 100dvh; background: var(--surface); }
.sidebar { width: 260px; flex-shrink: 0; background: var(--sidebar); display: flex; flex-direction: column; padding: 28px 14px 16px; }
.brand { display: flex; gap: 11px; align-items: center; padding: 0 12px 30px; text-decoration: none; font-size: 20px; font-weight: 600; letter-spacing: -.6px; }
.brand-mark { display: grid; place-items: center; width: 33px; height: 33px; border-radius: 10px; background: #242424; color: white; font-family: Georgia, serif; font-size: 23px; }
.brand small, .sidebar-footer small { display: block; color: var(--muted); font-size: 11px; font-weight: 400; letter-spacing: .3px; }
.nav-menu { display: grid; gap: 4px; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; color: var(--text); text-decoration: none; font-size: 14px; border-radius: 8px; }
.nav-item svg { width: 19px; height: 19px; }
.nav-item:hover, .nav-item.active { background: var(--hover); }
.conversation-slot { flex: 1; min-height: 0; display: flex; flex-direction: column; margin-top: 26px; }
.sidebar-footer { display: flex; align-items: center; gap: 10px; padding: 16px 10px 0; font-size: 12px; border-top: 1px solid var(--border); }
.workspace-avatar { display: grid; place-items: center; width: 32px; height: 32px; background: #e5e5e2; border-radius: 50%; }
.main-content { flex: 1; min-width: 0; overflow: hidden; position: relative; }
.mobile-menu, .sidebar-backdrop { display: none; }
@media(max-width: 760px) {
  .sidebar { position: fixed; inset: 0 auto 0 0; z-index: 30; visibility: hidden; transform: translateX(-100%); transition: transform .2s; }
  .sidebar.open { visibility: visible; transform: translateX(0); }
  .sidebar-backdrop { display: block; position: fixed; inset: 0; border: 0; background: #0005; z-index: 29; }
  .sidebar-backdrop:hover { background: #0005; }
  .mobile-menu { display: block; position: absolute; top: 16px; left: 14px; z-index: 10; padding: 5px 10px; }
}
</style>
