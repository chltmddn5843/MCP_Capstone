<script setup>
import { ref, onMounted } from 'vue'
import { get, post } from '../api'
import { FLAG, SAVINGS, won } from '../labels'
import TaskStream from '../components/TaskStream.vue'

const inv = ref([]), savings = ref(null), task = ref(null)
onMounted(async () => { inv.value = await get('/inventory'); try { savings.value = await get('/savings') } catch { savings.value = null } })
async function review() { const c = await post('/ai/tasks', { input: '안 쓰는 것으로 보이는 이용권을 검토해서 본인 확인이 필요한 사람과 재배정 가능한 좌석을 정리하고 처리 요청을 제안해줘', channel: 'admin_ui' }); task.value = c.task_id }
</script>

<template>
  <div class="page">
    <h2>이용권</h2>
    <p class="hint">사용 기록이 없다고 미사용으로 보지 않습니다. 본인에게 사용 의사를 묻고 반납 응답이 있을 때만 재배정합니다. 무응답은 회수 사유가 아닙니다.</p>
    <div v-for="i in inv" :key="i.contract.id" class="card">
      <h3 style="margin: 0 0 10px">{{ i.tool_name }} · {{ i.contract.plan_name }}</h3>
      <div class="metrics">
        <div class="metric"><div class="k">구매 좌석</div><div class="v">{{ i.purchased }}</div></div>
        <div class="metric"><div class="k">배정</div><div class="v">{{ i.assigned }}</div></div>
        <div class="metric"><div class="k">미배정</div><div class="v">{{ i.unassigned }}</div></div>
        <div class="metric"><div class="k">좌석 단가 (월)</div><div class="v">{{ won(i.contract.seat_price_krw) }}</div></div>
      </div>
      <b>확인이 필요한 이용권</b>
      <el-table :data="i.low_usage_candidates" size="small" style="margin-top: 6px">
        <el-table-column prop="employee_name" label="직원" width="120" />
        <el-table-column prop="dept_name" label="부서" width="110" />
        <el-table-column label="마지막 사용" width="130"><template #default="{ row }">{{ row.last_activity_at ? row.last_activity_at.slice(0, 10) : '기록 없음' }}</template></el-table-column>
        <el-table-column label="상태"><template #default="{ row }">{{ FLAG[row.flag] || row.flag }}</template></el-table-column>
        <el-table-column label="본인 확인" width="100"><template #default="{ row }">{{ row.needs_confirmation ? '필요' : '불필요' }}</template></el-table-column>
      </el-table>
    </div>
    <el-button type="primary" @click="review">안 쓰는 이용권 검토 요청</el-button>
    <TaskStream v-if="task" :key="task" :task-id="task" style="margin-top: 12px" />
    <div v-if="savings" class="card" style="margin-top: 16px">
      <h3 style="margin: 0 0 6px">절감 기록</h3>
      <p class="hint">아낀 구매 비용(재배정으로 안 산 좌석)과 실제로 줄어든 청구액을 구분해 기록합니다.</p>
      <el-table :data="[...Object.entries(savings.by_kind).map(([k, v]) => ({ k: SAVINGS[k] || k, v: won(v) })), { k: '합계', v: won(savings.total_krw) }]" size="small">
        <el-table-column prop="k" label="구분" /><el-table-column prop="v" label="금액" width="160" />
      </el-table>
    </div>
  </div>
</template>
