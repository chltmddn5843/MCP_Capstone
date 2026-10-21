<script setup>
// MVP: 시드 직원 선택 로그인(/auth/dev-login). 백엔드가 /auth/login(JWT)을 제공하면 아이디·비밀번호 폼으로 바꾼다.
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { post, ApiError } from '../api'
import { useAuth } from '../stores/auth'

const SEED = [['emp_asset_01', '최민준 · 관리자'], ['emp_mkt_01', '박서준 · 마케팅 직원'], ['emp_cs_01', '이지우 · 고객지원 직원'], ['emp_hrd_01', '김하나 · HRD 직원']]
const who = ref('emp_asset_01'), error = ref('')
const auth = useAuth(), router = useRouter()
async function login() {
  error.value = ''
  try { const d = await post('/auth/dev-login', { employee_id: who.value }); auth.set(d.access_token, d.employee); router.push('/') }
  catch (e) { error.value = e instanceof ApiError ? (e.code === 'network' ? e.message : `${e.label}: ${e.message}`) : String(e) }
}
</script>

<template>
  <div style="min-height: 100vh; display: grid; place-items: center">
    <div class="card" style="width: 380px">
      <h2 style="margin: 0 0 4px">한빛제조 AI·구독 운영</h2>
      <p class="hint">시연용 로그인. 사용자를 고르세요.</p>
      <el-select v-model="who" style="width: 100%; margin-bottom: 12px">
        <el-option v-for="[id, label] in SEED" :key="id" :value="id" :label="label" />
      </el-select>
      <el-button type="primary" style="width: 100%" @click="login">로그인</el-button>
      <el-alert v-if="error" type="error" :closable="false" :title="error" style="margin-top: 12px" />
    </div>
  </div>
</template>
