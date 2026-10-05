import { createRouter, createWebHistory } from 'vue-router'
import ChatView from './views/ChatView.vue'
import DashboardView from './views/DashboardView.vue'
import ReportView from './views/ReportView.vue'
import KnowledgeView from './views/KnowledgeView.vue'
import LLMOpsView from './views/LLMOpsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: ChatView },
    { path: '/dashboard', name: 'dashboard', component: DashboardView },
    { path: '/report', name: 'report', component: ReportView },
    { path: '/knowledge', name: 'knowledge', component: KnowledgeView },
    { path: '/llmops', name: 'llmops', component: LLMOpsView },
  ],
})

export default router
