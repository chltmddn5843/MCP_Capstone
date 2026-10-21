<script setup>
// 첫 관리자 가입. 회사가 아직 없을 때만 열린다(POST /setup/signup). 가입하면 바로 초기 설정 마법사(/setup)로 간다.
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { signup, setupStatus, errorLabel } from '../request.js'
import NodiLogo from '../components/NodiLogo.vue'

const router = useRouter()
const status = ref(null)
const f = ref({ company_name: '', admin_name: '', email: '', password: '', dept_name: '경영지원', job_title: 'IT 자산 관리자' })
const showPw = ref(false)
const busy = ref(false)
const error = ref('')
const bad = ref({})

onMounted(async () => {
  try { status.value = await setupStatus() } catch (e) { error.value = errorLabel(e) }
})

const RULES = {
  company_name: (v) => !v.trim() && '회사 이름을 입력하세요',
  admin_name: (v) => !v.trim() && '이름을 입력하세요',
  email: (v) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim()) && '회사 이메일 형식이 아닙니다 (예: admin@company.co.kr)',
  password: (v) => v.length < 8 && '비밀번호는 8자 이상이어야 합니다',
  dept_name: (v) => !v.trim() && '부서 이름을 입력하세요',
}
const check = (k) => { bad.value = { ...bad.value, [k]: RULES[k]?.(f.value[k]) || '' } }

async function submit() {
  Object.keys(RULES).forEach(check)
  const first = Object.keys(RULES).find((k) => bad.value[k])
  if (first) { document.getElementById(`su-${first}`)?.focus(); return }
  busy.value = true
  error.value = ''
  try {
    await signup({ ...f.value, email: f.value.email.trim() })
    router.replace('/setup')
  } catch (e) {
    error.value = e.code === 'conflict' ? e.message : errorLabel(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="signup">
    <div class="brand">
      <NodiLogo :size="32" /><span class="sr-only">nodi</span>
    </div>

    <section v-if="status?.company_name" class="card box">
      <h1>이미 등록된 회사가 있습니다</h1>
      <p class="small muted">{{ status.company_name }}은(는) 이미 가입했습니다. 관리자 계정으로 로그인하세요.</p>
      <RouterLink to="/login" class="btn btn-dark">로그인으로</RouterLink>
    </section>

    <form v-else class="card box" novalidate @submit.prevent="submit">
      <div class="head">
        <span class="xs muted">1 / 6 · 관리자 가입</span>
        <h1>회사 등록하기</h1>
        <p class="small muted">처음 한 번만 합니다. 가입한 분이 첫 관리자가 되고, 이어서 부서·구독 제품·AI 모델·예산을 차례로 설정합니다.</p>
      </div>

      <fieldset>
        <legend class="small">회사</legend>
        <label class="field">회사 이름
          <input id="su-company_name" v-model="f.company_name" autocomplete="organization" :aria-invalid="!!bad.company_name" :aria-describedby="bad.company_name ? 'e-company_name' : undefined" @blur="check('company_name')" />
          <span v-if="bad.company_name" id="e-company_name" class="err">{{ bad.company_name }}</span>
        </label>
      </fieldset>

      <fieldset>
        <legend class="small">첫 관리자</legend>
        <div class="two">
          <label class="field">이름
            <input id="su-admin_name" v-model="f.admin_name" autocomplete="name" :aria-invalid="!!bad.admin_name" :aria-describedby="bad.admin_name ? 'e-admin_name' : undefined" @blur="check('admin_name')" />
            <span v-if="bad.admin_name" id="e-admin_name" class="err">{{ bad.admin_name }}</span>
          </label>
          <label class="field">직함
            <input id="su-job_title" v-model="f.job_title" autocomplete="organization-title" />
          </label>
        </div>
        <label class="field">소속 부서 <span class="xs muted">다른 부서는 다음 단계에서 추가합니다</span>
          <input id="su-dept_name" v-model="f.dept_name" :aria-invalid="!!bad.dept_name" :aria-describedby="bad.dept_name ? 'e-dept_name' : undefined" @blur="check('dept_name')" />
          <span v-if="bad.dept_name" id="e-dept_name" class="err">{{ bad.dept_name }}</span>
        </label>
        <label class="field">회사 이메일 <span class="xs muted">로그인 아이디로 씁니다</span>
          <input id="su-email" v-model="f.email" type="email" autocomplete="username" inputmode="email" :aria-invalid="!!bad.email" :aria-describedby="bad.email ? 'e-email' : undefined" @blur="check('email')" />
          <span v-if="bad.email" id="e-email" class="err">{{ bad.email }}</span>
        </label>
        <label class="field">비밀번호 <span class="xs muted">8자 이상</span>
          <span class="pw">
            <input id="su-password" v-model="f.password" :type="showPw ? 'text' : 'password'" autocomplete="new-password" :aria-invalid="!!bad.password" :aria-describedby="bad.password ? 'e-password' : undefined" @blur="check('password')" />
            <button type="button" class="reveal" :aria-pressed="showPw" @click="showPw = !showPw">{{ showPw ? '숨기기' : '보기' }}</button>
          </span>
          <span v-if="bad.password" id="e-password" class="err">{{ bad.password }}</span>
        </label>
      </fieldset>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" class="btn btn-dark submit" :disabled="busy || !status">{{ busy ? '등록하는 중…' : '가입하고 설정 시작' }}</button>
      <p class="xs muted" style="margin: 0">이미 계정이 있나요? <RouterLink to="/login">로그인</RouterLink></p>
    </form>
  </main>
</template>

<style scoped>
.signup { min-height: 100dvh; display: flex; flex-direction: column; align-items: center; gap: 24px; padding: 40px 16px; background: var(--paper); word-break: keep-all; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; }
.box { width: 100%; max-width: 520px; padding: 32px; gap: 20px; }
.head { display: flex; flex-direction: column; gap: 6px; }
.head h1, .box > h1 { font-size: 24px; }
fieldset { margin: 0; padding: 0; border: 0; display: flex; flex-direction: column; gap: 14px; }
legend { font-weight: 700; padding-bottom: 10px; }
.two { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.field input { min-height: 48px; border-radius: 10px; border: 1px solid var(--line-strong); background: var(--white); padding: 0 14px; font-size: 16px; font-weight: 400; width: 100%; }
.field input[aria-invalid='true'] { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink); }
.err { font-size: 12px; font-weight: 600; align-self: flex-start; padding: 2px 8px; border-radius: 6px; background: var(--ink); color: var(--lime); }
.pw { position: relative; display: block; }
.pw input { padding-right: 72px; }
.reveal { position: absolute; right: 6px; top: 6px; height: 36px; padding: 0 10px; border: 0; border-radius: 8px; background: var(--paper); font-size: 12px; font-weight: 600; }
.error { margin: 0; font-size: 13px; padding: 10px 12px; border-radius: 10px; background: var(--ink); color: var(--lime); }
.submit { width: 100%; min-height: 50px; font-size: 15px; }
</style>
