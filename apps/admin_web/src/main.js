import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './styles.css'

const routes = [
  { path: '/', name: 'home', component: () => import('./views/HomeView.vue'), meta: { title: '홈' } },
  { path: '/inbox', name: 'inbox', component: () => import('./views/InboxView.vue'), meta: { title: '승인 대기' } },
  { path: '/licenses', name: 'licenses', component: () => import('./views/LicensesView.vue'), meta: { title: '구독·이용권' } },
  { path: '/cost', name: 'cost', component: () => import('./views/CostView.vue'), meta: { title: '비용·사용량' } },
  { path: '/suggestions', name: 'suggestions', component: () => import('./views/SuggestionsView.vue'), meta: { title: '자동 제안 기록' } },
  { path: '/needs', name: 'needs', component: () => import('./views/NeedsView.vue'), meta: { title: '미지원 요청·팀 활용' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })
router.afterEach((to) => { document.title = `${to.meta.title} · 구독 운영` })

createApp(App).use(router).mount('#app')
