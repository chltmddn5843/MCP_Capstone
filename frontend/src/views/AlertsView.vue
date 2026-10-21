<script setup>
import { ref, onMounted } from 'vue'
import { get, post } from '../api'
import { ANOMALY_STATUS, won } from '../labels'
import TaskStream from '../components/TaskStream.vue'

const items = ref([]), tasks = ref({})
onMounted(async () => { items.value = await get('/anomalies') })
async function investigate(a) {
  const c = await post('/ai/tasks', { input: `알림 ${a.id}의 원인을 조사하고 처리 방법을 제안해줘`, prompt_name: 'investigate_anomaly', prompt_args: { anomaly_id: a.id }, channel: 'admin_ui' })
  tasks.value[a.id] = c.task_id
}
</script>

<template>
  <div class="page">
    <h2>비용 급증 알림</h2>
    <p class="hint">사용량을 원화로 환산해 기준치(최근 평균)의 몇 배인지 검사합니다. '원인 조사'를 누르면 AI 비서가 프로젝트 목적과 모델·입력 길이·API 키별 분포를 보고 원인 후보와 처리 방법을 제시합니다.</p>
    <div v-for="a in items" :key="a.id" class="card">
      <div class="row" style="justify-content: space-between">
        <div><b>{{ a.scope_name || a.scope_id }}</b> <el-tag size="small">{{ ANOMALY_STATUS[a.status] || a.status }}</el-tag></div>
        <div class="row">
          <div class="metric"><div class="k">기준 대비</div><div class="v">{{ a.ratio }}배</div></div>
          <div class="metric"><div class="k">예상 월 비용</div><div class="v">{{ won(a.projected_monthly_cost?.krw) }}</div></div>
          <el-button type="primary" @click="investigate(a)">원인 조사</el-button>
        </div>
      </div>
      <TaskStream v-if="tasks[a.id]" :key="tasks[a.id]" :task-id="tasks[a.id]" style="margin-top: 12px" />
    </div>
    <p v-if="!items.length" class="muted">알림이 없습니다.</p>
  </div>
</template>
