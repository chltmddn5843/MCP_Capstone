<script setup>
// 승인 대기: 처리 요청 결정 + AI 비서 처리 확인
import { ref, onMounted } from 'vue'
import { get, post, ApiError } from '../api'
import { PLAN_TYPE, RISK, TOOL, dt } from '../labels'
import TaskStream from './TaskStream.vue'
import { ElMessage } from 'element-plus'

const plans = ref([]), waiting = ref([]), reasons = ref({}), resumed = ref({})
async function load() {
  const page = await get('/plans', { status: 'pending_approval' })
  plans.value = page.items
  try { waiting.value = (await get('/ai/tasks', { mine: false, limit: 50 })).filter(t => t.status === 'waiting_approval') } catch { waiting.value = [] }
}
async function decide(p, approve) {
  const reason = (reasons.value[p.id] || '').trim()
  if (!reason) return ElMessage.warning('결정 사유를 적어 주세요')
  try { await post(`/plans/${p.id}/${approve ? 'approve' : 'reject'}`, { reason }); ElMessage.success(approve ? '승인했습니다' : '반려했습니다'); await load() }
  catch (e) { ElMessage.error(e instanceof ApiError ? `${e.label}: ${e.message}` : String(e)) }
}
async function decideTask(t, approved) {
  const reason = (reasons.value[t.task_id] || '').trim()
  if (!reason) return ElMessage.warning('결정 사유를 적어 주세요')
  try { await post(`/ai/tasks/${t.task_id}/approval`, { approved, reason }); resumed.value[t.task_id] = t.tool_calls.length * 2 + 1; waiting.value = waiting.value.filter(x => x.task_id !== t.task_id) }
  catch (e) { ElMessage.error(e instanceof ApiError ? `${e.label}: ${e.message}` : String(e)) }
}
onMounted(load)
defineExpose({ load })
</script>

<template>
  <h3>승인 대기 요청</h3>
  <p class="hint">'담당자 승인' 요청은 승인하면 처리됩니다. '책임자 결정' 요청(구매, 운영 환경 변경)은 결정만 기록하고 처리는 시스템 밖에서 합니다.</p>
  <div v-for="p in plans" :key="p.id" class="card">
    <div class="row"><b>{{ PLAN_TYPE[p.type] || p.type }}</b><el-tag size="small">{{ RISK[p.risk_level] }}</el-tag><span class="muted">요청자 {{ p.requested_by }} · {{ dt(p.created_at) }}</span></div>
    <div style="margin: 6px 0">{{ p.rationale }}</div>
    <el-collapse><el-collapse-item title="대상과 참고한 데이터"><pre style="font-size: 12px">{{ JSON.stringify({ 대상: p.items, '참고한 데이터': p.evidence }, null, 2) }}</pre></el-collapse-item></el-collapse>
    <div class="row" style="margin-top: 8px">
      <el-input v-model="reasons[p.id]" placeholder="결정 사유 (필수)" style="max-width: 360px" />
      <el-button type="primary" @click="decide(p, true)">승인</el-button>
      <el-button @click="decide(p, false)">반려</el-button>
    </div>
  </div>
  <p v-if="!plans.length" class="muted">승인 대기 중인 요청이 없습니다.</p>

  <h3 style="margin-top: 24px">AI 비서 처리 확인</h3>
  <p class="hint">AI 비서가 실제 변경을 하기 직전에 멈춘 건입니다. 확인하면 그 지점부터 이어서 처리합니다.</p>
  <div v-for="t in waiting" :key="t.task_id" class="card">
    <div><b>{{ t.approval.summary }}</b></div>
    <div class="muted">요청: {{ t.input }} · 요청자 {{ t.requester_id }} · 단계: {{ TOOL[t.approval.tool_name] || t.approval.tool_name }}</div>
    <div class="row" style="margin-top: 8px">
      <el-input v-model="reasons[t.task_id]" placeholder="결정 사유 (필수)" style="max-width: 360px" />
      <el-button type="primary" @click="decideTask(t, true)">확인하고 처리</el-button>
      <el-button @click="decideTask(t, false)">거절</el-button>
    </div>
  </div>
  <p v-if="!waiting.length && !Object.keys(resumed).length" class="muted">확인을 기다리는 AI 비서 작업이 없습니다.</p>
  <TaskStream v-for="(after, id) in resumed" :key="id" :task-id="id" :after="after" />
</template>
