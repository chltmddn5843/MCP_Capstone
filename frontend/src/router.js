import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './stores/auth'

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  { path: '/', redirect: () => (useAuth().isAdmin ? '/licenses' : '/assistant') },
  { path: '/licenses', component: () => import('./views/LicensesView.vue'), meta: { admin: true, title: '이용권' } },
  { path: '/alerts', component: () => import('./views/AlertsView.vue'), meta: { admin: true, title: '비용 급증 알림' } },
  { path: '/approvals', component: () => import('./views/ApprovalsView.vue'), meta: { admin: true, title: '승인 대기' } },
  { path: '/unmet', component: () => import('./views/UnmetView.vue'), meta: { admin: true, title: '미지원 요청' } },
  { path: '/adoption', component: () => import('./views/AdoptionView.vue'), meta: { admin: true, title: '활용 현황·자동 제안' } },
  { path: '/assistant', component: () => import('./views/AssistantView.vue'), meta: { title: 'AI 비서' } },
  { path: '/mine', component: () => import('./views/MyTasksView.vue'), meta: { employee: true, title: '내 업무와 이용권' } },
  { path: '/history', component: () => import('./views/HistoryView.vue'), meta: { title: '내 요청' } },
]

const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(to => {
  const auth = useAuth()
  if (!to.meta.public && !auth.loggedIn) return '/login'
  if (to.meta.admin && !auth.isAdmin) return '/assistant'
  return true
})
export default router
