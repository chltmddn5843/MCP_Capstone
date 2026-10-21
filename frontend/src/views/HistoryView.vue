<script setup>
import { ref, onMounted } from 'vue'
import { get } from '../api'
import { TASK_STATUS, TOOL, dt } from '../labels'
const tasks = ref([])
onMounted(async () => { tasks.value = await get('/ai/tasks', { mine: true, limit: 20 }) })
</script>
<template>
  <div class="page">
    <h2>내 요청</h2>
    <el-collapse>
      <el-collapse-item v-for="t in tasks" :key="t.task_id" :title="`${dt(t.created_at)} · ${TASK_STATUS[t.status] || t.status} · ${t.input.slice(0, 50)}`">
        <div v-if="t.result" class="answer">{{ t.result.answer }}</div>
        <el-alert v-if="t.status === 'waiting_approval' && t.approval" type="warning" :closable="false" :title="'관리자 확인 대기: ' + t.approval.summary" />
        <el-alert v-if="t.error" type="error" :closable="false" :title="t.error" />
        <div class="muted" style="margin-top: 6px">처리 단계: {{ t.tool_calls.map(c => (TOOL[c.name] || c.name) + (c.error ? ' ⚠️' : '')).join(' → ') || '없음' }}</div>
      </el-collapse-item>
    </el-collapse>
    <p v-if="!tasks.length" class="muted">아직 요청이 없습니다.</p>
  </div>
</template>
