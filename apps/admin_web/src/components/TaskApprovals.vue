<script setup>
// AI 비서 처리 확인: 변경 도구 앞에서 멈춘 작업을 관리자가 확인·거절하면 그 지점부터 이어서 처리한다. InboxView 아래에 붙는다.
import { ref, onMounted } from 'vue'
import { getTasks, approveTask, errorLabel } from '../request.js'
import { TOOL_LABEL } from '../labels.js'
import TaskStream from './TaskStream.vue'

const waiting = ref([]), reasons = ref({}), resumed = ref({}), notice = ref('')
async function load() { try { waiting.value = (await getTasks(false, 50)).filter((t) => t.status === 'waiting_approval') } catch (e) { notice.value = errorLabel(e) } }
async function decide(t, approved) {
  const reason = (reasons.value[t.task_id] ?? '').trim()
  if (!reason) { notice.value = '결정 사유를 적어 주세요.'; return }
  try {
    await approveTask(t.task_id, approved, reason)
    resumed.value[t.task_id] = t.tool_calls.length * 2 + 1
    waiting.value = waiting.value.filter((x) => x.task_id !== t.task_id)
    notice.value = ''
  } catch (e) { notice.value = errorLabel(e) }
}
onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="card" aria-labelledby="task-ap-h" style="gap: 12px">
    <div class="card-head">
      <div><h2 id="task-ap-h">AI 비서 처리 확인</h2><span class="small muted">AI 비서가 실제 변경을 하기 직전에 멈춘 건입니다. 확인하면 그 지점부터 이어서 처리합니다.</span></div>
      <button type="button" class="btn btn-sm" @click="load">새로 고침</button>
    </div>
    <p v-if="notice" class="status" role="status">{{ notice }}</p>
    <div v-for="t in waiting" :key="t.task_id" class="inset" style="gap: 8px">
      <strong style="font-size: 14px">{{ t.approval.summary }}</strong>
      <span class="xs muted">요청: {{ t.input }} · 요청자 {{ t.requester_id }} · 단계: {{ TOOL_LABEL[t.approval.tool_name] ?? t.approval.tool_name }}</span>
      <div class="tags" style="gap: 8px; align-items: center">
        <input v-model="reasons[t.task_id]" class="reason" placeholder="결정 사유 (필수 · 요청한 직원에게 전달됩니다)" />
        <button type="button" class="btn btn-dark btn-sm" @click="decide(t, true)">확인하고 처리</button>
        <button type="button" class="btn btn-sm" @click="decide(t, false)">거절</button>
      </div>
    </div>
    <p v-if="!waiting.length && !Object.keys(resumed).length" class="small muted" style="margin: 0">확인을 기다리는 AI 비서 작업이 없습니다.</p>
    <TaskStream v-for="(after, id) in resumed" :key="id" :task-id="id" :after="after" />
  </section>
</template>

<style scoped>
.reason { flex: 1 1 240px; min-height: 40px; padding: 0 12px; border: 1px solid rgba(17, 17, 19, 0.16); border-radius: 10px; background: var(--white); font-size: 14px; }
</style>
