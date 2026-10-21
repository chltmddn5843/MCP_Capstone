<script setup>
import { ref, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { getCounts, getMe } from './api.js'

const route = useRoute()
const me = ref({ name: '', role: '' })
const counts = ref({ inbox: 0, cost: 0 })
const mainEl = ref(null)

const groups = [
  { label: '운영', items: [
    { to: '/', label: '홈', icon: ['M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z'] },
    { to: '/inbox', label: '승인 대기', badge: 'inbox', icon: ['M4 13l2-8h12l2 8', 'M4 13v6h16v-6h-5l-1 2h-4l-1-2z'] },
    { to: '/licenses', label: '구독·이용권', icon: ['M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z', 'M7 10h4M7 14h7'] },
    { to: '/cost', label: '비용·사용량', badge: 'cost', icon: ['M4 20V10M10 20V4M16 20v-7M22 20H2'] },
  ] },
  { label: '활용 지원', items: [
    { to: '/suggestions', label: '자동 제안 기록', icon: ['M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z', 'M9 11h6M9 14h4'] },
    { to: '/needs', label: '미지원 요청·팀 활용', icon: ['M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z', 'M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01'] },
  ] },
]

getMe().then((v) => (me.value = v))
// 처리 요청을 승인·생성하면 배지가 바뀌므로 화면을 옮길 때마다 다시 센다.
watch(() => route.fullPath, async (_, prev) => {
  counts.value = await getCounts()
  if (prev) { await nextTick(); mainEl.value?.focus() }
}, { immediate: true })
</script>

<template>
  <a class="skip" href="#main">본문으로 건너뛰기</a>
  <div class="layout">
    <nav class="sidebar" aria-label="관리자 메뉴">
      <div class="brand">
        <div class="logo" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h4l3-7 3 14 3-7h3" /></svg>
        </div>
        <div><strong>구독 운영</strong><span>A 코스메틱</span></div>
      </div>

      <div v-for="g in groups" :key="g.label" class="group">
        <span class="group-label">{{ g.label }}</span>
        <RouterLink v-for="it in g.items" :key="it.to" :to="it.to" class="nav-item">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-for="d in it.icon" :key="d" :d="d" /></svg>
          <span class="nav-label">{{ it.label }}</span>
          <span v-if="it.badge && counts[it.badge]" class="badge">
            {{ counts[it.badge] }}<span class="sr-only">건</span>
          </span>
        </RouterLink>
      </div>

      <div class="foot">
        <button type="button" class="btn btn-primary ask">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" /></svg>
          AI 비서에게 묻기
        </button>
        <div class="me">
          <div class="avatar" aria-hidden="true">{{ me.name.slice(0, 1) }}</div>
          <div><strong>{{ me.name }}</strong><span>{{ me.role }}</span></div>
        </div>
      </div>
    </nav>

    <main id="main" ref="mainEl" class="main" tabindex="-1">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.skip { position: absolute; left: 16px; top: -48px; z-index: 10; padding: 10px 14px; border-radius: 10px; background: var(--lime); font-weight: 700; }
.skip:focus { top: 16px; }
.main:focus { outline: none; }
.sidebar { background: var(--ink); color: var(--white); padding: 24px 16px; display: flex; flex-direction: column; gap: 28px; position: sticky; top: 0; height: 100dvh; overflow-y: auto; }
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px; }
.brand div:last-child, .me div:last-child { display: flex; flex-direction: column; }
.brand strong { font-size: 15px; }
.brand span, .me span { font-size: 12px; color: var(--muted-on-ink); }
.logo { width: 28px; height: 28px; border-radius: 8px; background: var(--lime); color: var(--ink); display: grid; place-items: center; }
.group { display: flex; flex-direction: column; gap: 4px; }
.group-label { font-size: 12px; font-weight: 500; color: rgba(255, 255, 255, 0.56); padding: 0 12px 6px; }
.nav-item { display: flex; align-items: center; gap: 12px; min-height: 44px; padding: 0 12px; border-radius: 10px; text-decoration: none; font-size: 14px; font-weight: 500; color: rgba(255, 255, 255, 0.8); }
.nav-item:hover { background: rgba(255, 255, 255, 0.08); color: var(--white); }
.nav-item.router-link-exact-active { background: var(--lime); color: var(--ink); }
.nav-label { flex: 1; }
.badge { min-width: 22px; height: 22px; padding: 0 7px; border-radius: 999px; font-size: 12px; font-weight: 700; display: grid; place-items: center; background: var(--lime); color: var(--ink); }
.router-link-exact-active .badge { background: var(--ink); color: var(--lime); }
.foot { margin-top: auto; display: flex; flex-direction: column; gap: 12px; }
.ask { width: 100%; }
.me { display: flex; align-items: center; gap: 10px; padding: 12px 8px 0; border-top: 1px solid rgba(255, 255, 255, 0.12); }
.me strong { font-size: 13px; }
.avatar { width: 32px; height: 32px; border-radius: 999px; background: var(--white); color: var(--ink); font-size: 13px; font-weight: 700; display: grid; place-items: center; }
@media (max-width: 900px) {
  .sidebar { position: static; height: auto; gap: 16px; }
  .group { flex-direction: row; flex-wrap: wrap; }
  .group-label { width: 100%; padding-bottom: 0; }
  .foot { flex-direction: row; flex-wrap: wrap; align-items: center; }
  .ask { width: auto; }
  .me { border-top: 0; padding: 0; }
}
</style>
