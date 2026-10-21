<script setup>
// 로그인. 화면은 backend /auth/login만 부른다 (통신 구조: 브라우저 → /api → backend).
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, devLogin, errorLabel } from '../request.js'

const route = useRoute()
const router = useRouter()
const loginId = ref('')
const password = ref('')
const showPw = ref(false)
const busy = ref(false)
const error = ref('')
const isDev = import.meta.env.DEV
// 개발 서버에서만 보이는 시연 계정 (db/seed/seed.py)
const DEMO = [
  { id: 'emp_asset_01', name: '최민준', role: '관리자 · IT 자산·보안' },
  { id: 'emp_mkt_01', name: '박서준', role: '직원 · 마케팅' },
  { id: 'emp_cs_01', name: '이지우', role: '직원 · 고객지원' },
]
const FEATURES = [
  ['업데이트 활용 제안', '새 기능 중 우리 팀 업무에 맞는 것만 골라 알려요'],
  ['업무별 모델 추천', '품질 기준을 통과한 모델 중 비용이 낮은 것을 근거와 함께'],
  ['비용 급증 알림', '사용량이 튀면 원인 후보와 대응안을 먼저 정리해요'],
  ['이용권 운영', '남은 좌석은 바로 배정, 없으면 AI 의견과 함께 승인 대기'],
]

async function done(fn) {
  busy.value = true
  error.value = ''
  try {
    await fn()
    router.replace(route.query.next || '/')
  } catch (e) {
    error.value = e.code === 'unauthorized' || e.code === 'forbidden' ? e.message : errorLabel(e)
  } finally {
    busy.value = false
  }
}
function submit() {
  if (!loginId.value.trim() || !password.value) { error.value = '사번(또는 이메일)과 비밀번호를 모두 입력하세요'; return }
  done(() => login(loginId.value.trim(), password.value))
}
</script>

<template>
  <div class="login">
    <section class="hero" aria-labelledby="hero-h">
      <div class="brand">
        <div class="logo" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h4l3-7 3 14 3-7h3" /></svg>
        </div>
        <span>구독 운영 · 한빛제조</span>
      </div>
      <div class="pitch">
        <h1 id="hero-h">회사가 쓰는 AI를<br /><mark>업무에 맞게</mark></h1>
        <p>직원은 업무에 맞는 제품과 모델을 안내받고, 관리자는 이용권과 비용을 한 화면에서 챙깁니다.</p>
      </div>
      <ol class="features">
        <li v-for="([t, d], i) in FEATURES" :key="t">
          <span class="num" aria-hidden="true">F{{ i + 1 }}</span>
          <div><strong>{{ t }}</strong><span>{{ d }}</span></div>
        </li>
      </ol>
    </section>

    <section class="panel" aria-labelledby="form-h">
      <form class="card form" novalidate @submit.prevent="submit">
        <div class="head">
          <h2 id="form-h">로그인</h2>
          <p class="small muted">사번 또는 회사 이메일로 로그인하세요.</p>
        </div>
        <label class="field">사번 또는 이메일
          <input id="login-id" v-model="loginId" type="text" autocomplete="username" placeholder="예: emp_mkt_01" :aria-invalid="!!error" required />
        </label>
        <label class="field">비밀번호
          <span class="pw">
            <input id="login-pw" v-model="password" :type="showPw ? 'text' : 'password'" autocomplete="current-password" :aria-invalid="!!error" required />
            <button type="button" class="reveal" :aria-pressed="showPw" @click="showPw = !showPw">{{ showPw ? '숨기기' : '보기' }}</button>
          </span>
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button type="submit" class="btn btn-dark submit" :disabled="busy">{{ busy ? '확인하는 중…' : '로그인' }}</button>
        <p class="xs muted">5번 틀리면 5분 동안 잠겨요. 로그인은 1시간 동안 유지됩니다.</p>
      </form>

      <div v-if="isDev" class="demo">
        <span class="xs muted">개발 서버 전용 · 시연 계정으로 바로 들어가기</span>
        <div class="tags">
          <button v-for="d in DEMO" :key="d.id" type="button" class="chip" :disabled="busy" @click="done(() => devLogin(d.id))">
            <strong>{{ d.name }}</strong>&nbsp;<span class="muted">{{ d.role }}</span>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login { word-break: keep-all; min-height: 100dvh; display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); background: var(--paper); }
.hero { background: var(--ink); color: var(--white); padding: 40px 56px; display: flex; flex-direction: column; gap: 48px; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--muted-on-ink); }
.logo { width: 32px; height: 32px; border-radius: 9px; background: var(--lime); color: var(--ink); display: grid; place-items: center; }
.pitch { display: flex; flex-direction: column; gap: 16px; max-width: 560px; word-break: keep-all; }
.pitch h1 { font-size: clamp(32px, 4.4vw, 52px); line-height: 1.12; letter-spacing: -0.03em; text-wrap: balance; }
.pitch mark { background: var(--lime); color: var(--ink); padding: 0 0.12em; border-radius: 6px; }
.pitch p { color: var(--muted-on-ink); font-size: 16px; line-height: 1.6; max-width: 34ch; margin: 0; }
.features { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.features li { display: flex; gap: 12px; padding: 16px; border-radius: 14px; border: 1px solid rgba(255, 255, 255, 0.12); }
.features li div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.features strong { font-size: 14px; }
.features li span:not(.num) { font-size: 12.5px; color: var(--muted-on-ink); line-height: 1.5; }
.num { flex: none; width: 30px; height: 22px; border-radius: 6px; background: var(--lime); color: var(--ink); font-size: 11px; font-weight: 700; display: grid; place-items: center; }
.panel { display: flex; flex-direction: column; justify-content: center; gap: 20px; padding: 40px max(24px, 6vw); }
.form { max-width: 420px; width: 100%; gap: 18px; padding: 32px; }
.head { display: flex; flex-direction: column; gap: 4px; }
.head h2 { font-size: 24px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.field input { min-height: 48px; border-radius: 10px; border: 1px solid var(--line-strong); background: var(--white); padding: 0 14px; font-size: 15px; font-weight: 400; width: 100%; }
.field input:focus-visible { outline: 2px solid var(--ink); outline-offset: 1px; border-color: var(--ink); }
.field input[aria-invalid='true'] { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink); }
.pw { position: relative; display: block; }
.pw input { padding-right: 72px; }
.reveal { position: absolute; right: 6px; top: 6px; height: 36px; padding: 0 10px; border: 0; border-radius: 8px; background: var(--paper); font-size: 12px; font-weight: 600; }
.error { margin: 0; font-size: 13px; padding: 10px 12px; border-radius: 10px; background: var(--ink); color: var(--lime); }
.submit { width: 100%; min-height: 50px; font-size: 15px; }
.demo { max-width: 420px; width: 100%; display: flex; flex-direction: column; gap: 8px; }
.demo .chip { display: inline-flex; align-items: center; }
@media (max-width: 900px) {
  .login { grid-template-columns: 1fr; }
  .hero { padding: 28px 20px; gap: 28px; }
  .features { grid-template-columns: 1fr; }
  .panel { padding: 28px 16px 40px; }
  .form { padding: 24px; }
}
</style>
