<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './stores/auth'
import { ROLE } from './labels'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const adminMenu = [['/licenses', '이용권'], ['/alerts', '비용 급증 알림'], ['/approvals', '승인 대기'], ['/unmet', '미지원 요청'], ['/adoption', '활용 현황·자동 제안'], ['/assistant', 'AI 비서'], ['/history', '내 요청']]
const employeeMenu = [['/assistant', 'AI 비서'], ['/mine', '내 업무와 이용권'], ['/history', '내 요청']]
const menu = computed(() => (auth.isAdmin ? adminMenu : employeeMenu))
function logout() { auth.logout(); router.push('/login') }
</script>

<template>
  <el-container v-if="auth.loggedIn && route.path !== '/login'" style="min-height: 100vh">
    <el-aside width="220px" style="background: #1f2937; color: #e5e7eb; padding: 16px 0">
      <div style="padding: 0 20px 16px; font-weight: 600; font-size: 15px">한빛제조 AI·구독 운영</div>
      <el-menu :default-active="route.path" router background-color="#1f2937" text-color="#d1d5db" active-text-color="#fff">
        <el-menu-item v-for="[p, label] in menu" :key="p" :index="p">{{ label }}</el-menu-item>
      </el-menu>
      <div style="padding: 20px; font-size: 12px; color: #9ca3af">
        <div style="color: #e5e7eb; font-size: 13px">{{ auth.me.name }} · {{ auth.me.job_title }}</div>
        <div>{{ auth.me.dept_name }} · {{ ROLE[auth.role] }}</div>
        <el-button link size="small" style="margin-top: 8px; color: #93c5fd" @click="logout">다른 사용자로 로그인</el-button>
      </div>
    </el-aside>
    <el-main style="padding: 0"><router-view /></el-main>
  </el-container>
  <router-view v-else />
</template>
