<script setup>
import { ref, onMounted } from 'vue'
import { get, post } from '../api'
import { SUGGESTION_STATUS } from '../labels'
import TaskStream from '../components/TaskStream.vue'

const teams = ref([]), updates = ref([]), suggestions = ref([]), tasks = ref({})
async function load() {
  teams.value = await get('/adoption/teams')
  updates.value = (await get('/updates')).items
  suggestions.value = (await get('/suggestions')).items
}
onMounted(load)
async function review(u) {
  const c = await post('/ai/tasks', { input: `업데이트 ${u.id}를 검토해서 관련 팀 업무에 활용 제안을 만들어줘`, prompt_name: 'review_update', prompt_args: { update_id: u.id }, channel: 'admin_ui' })
  tasks.value[u.id] = c.task_id
}
</script>

<template>
  <div class="page">
    <h2>활용 현황·자동 제안</h2>
    <p class="hint">개인이 특정되지 않도록 5명 이상 팀만, 팀 단위로만 보여 줍니다. 활용 데이터는 교육과 제품 개선에만 쓰고 인사평가에 쓰지 않습니다.</p>
    <el-table :data="teams" size="small" class="card">
      <el-table-column prop="team_name" label="팀" width="110" /><el-table-column prop="headcount" label="인원" width="70" />
      <el-table-column prop="suggestions_sent" label="보낸 제안" width="90" /><el-table-column prop="useful" label="도움 됨" width="80" />
      <el-table-column prop="irrelevant" label="관련 없음" width="90" /><el-table-column prop="questions" label="적용 방법 질문" width="120" />
      <el-table-column label="AI 활동 인원 비율" width="130"><template #default="{ row }">{{ Math.round(row.active_ratio * 100) }}%</template></el-table-column>
      <el-table-column label="반복 질문"><template #default="{ row }">{{ row.top_questions.join(' / ') || '-' }}</template></el-table-column>
    </el-table>
    <h3>최근 제품 업데이트와 자동 제안</h3>
    <p class="hint">허용 목록 벤더의 공식 릴리스 노트만 수집합니다. 새 항목이 있으면 시스템이 관련 팀을 판단해 알림 정책 안에서 팀 Slack으로 자동 발송합니다. '지금 검토'는 같은 판단을 바로 실행합니다.</p>
    <div v-for="u in updates" :key="u.id" class="card">
      <div class="row" style="justify-content: space-between">
        <div><b>{{ u.vendor }} · {{ u.title }}</b> <span class="muted">{{ u.published_at.slice(0, 10) }}</span><div>{{ u.summary }} <a :href="u.url" target="_blank">원문 보기</a></div></div>
        <el-button @click="review(u)">지금 검토</el-button>
      </div>
      <TaskStream v-if="tasks[u.id]" :key="tasks[u.id]" :task-id="tasks[u.id]" style="margin-top: 12px" />
    </div>
    <h3>자동 제안 기록</h3>
    <p class="hint">어느 팀에 뭘 보냈고, 왜 보내지 않았는지 남깁니다.</p>
    <el-table :data="suggestions" size="small">
      <el-table-column prop="update_id" label="업데이트" width="200" />
      <el-table-column label="대상" width="180"><template #default="{ row }">{{ row.target_type }} {{ row.target_id || '' }}</template></el-table-column>
      <el-table-column label="상태" width="100"><template #default="{ row }">{{ SUGGESTION_STATUS[row.status] || row.status }}</template></el-table-column>
      <el-table-column label="보낸 이유"><template #default="{ row }">{{ row.relevance || '-' }}</template></el-table-column>
      <el-table-column label="보내지 않은 이유"><template #default="{ row }">{{ row.hold_reason || '-' }}</template></el-table-column>
    </el-table>
  </div>
</template>
