<script setup>
// 에이전트 작업 하나의 진행 상황. TOOL_START/END → 단계, TOKEN → 답변, APPROVAL_REQUIRED → 안내, DONE → 답과 참고한 데이터.
import { ref, onBeforeUnmount } from 'vue'
import { streamTask, ApiError } from '../api'
import { TOOL, ERROR_CODE } from '../labels'

const props = defineProps({ taskId: String, after: { type: Number, default: 0 } })
const emit = defineEmits(['done', 'approval'])
const steps = ref([]), answer = ref(''), evidence = ref([]), status = ref('running'), error = ref(''), approval = ref(null)
const ctrl = new AbortController()

async function run() {
  try {
    await streamTask(props.taskId, props.after, ev => {
      if (ev.type === 'TOOL_START') steps.value.push({ id: ev.tool_call.id, text: `${TOOL[ev.tool_call.name] || ev.tool_call.name} 중…`, state: 'run' })
      else if (ev.type === 'TOOL_END') {
        const s = steps.value.find(x => x.id === ev.tool_call.id)
        let msg = ''
        if (ev.tool_call.error) { try { msg = ERROR_CODE[JSON.parse(ev.tool_call.output).error.code] || ev.tool_call.error } catch { msg = ev.tool_call.error } }
        if (s) { s.text = `${TOOL[ev.tool_call.name] || ev.tool_call.name}${msg ? ': ' + msg : ' 완료'}`; s.state = msg ? 'warn' : 'ok' }
      }
      else if (ev.type === 'TOKEN') answer.value += ev.text
      else if (ev.type === 'APPROVAL_REQUIRED') { status.value = 'waiting'; approval.value = ev.approval; emit('approval', ev) }
      else if (ev.type === 'DONE') { status.value = 'done'; answer.value = ev.result.answer; evidence.value = ev.result.evidence || []; emit('done', ev) }
      else if (ev.type === 'FAILED') { status.value = 'failed'; error.value = ev.error }
    }, ctrl.signal)
  } catch (e) {
    if (e.name === 'AbortError') return
    status.value = 'failed'; error.value = e instanceof ApiError ? e.message : String(e)
  }
}
run()
onBeforeUnmount(() => ctrl.abort())
</script>

<template>
  <div class="card">
    <div class="row" style="margin-bottom: 8px">
      <el-tag v-if="status === 'running'" type="info">AI 비서가 처리하고 있습니다…</el-tag>
      <el-tag v-else-if="status === 'waiting'" type="warning">관리자 확인 대기</el-tag>
      <el-tag v-else-if="status === 'done'" type="success">완료</el-tag>
      <el-tag v-else type="danger">실패</el-tag>
    </div>
    <div class="steps">
      <div v-for="s in steps" :key="s.id">{{ s.state === 'run' ? '🔎' : s.state === 'ok' ? '✅' : '⚠️' }} {{ s.text }}</div>
    </div>
    <el-alert v-if="approval" type="warning" :closable="false" style="margin: 10px 0" :title="'관리자 확인이 필요한 단계입니다. ' + approval.summary" description="승인 대기 화면에서 확인하면 이어서 자동 처리됩니다." />
    <div v-if="answer" class="answer" style="margin-top: 10px">{{ answer }}</div>
    <el-alert v-if="error" type="error" :closable="false" :title="error" style="margin-top: 10px" />
    <el-collapse v-if="evidence.length" style="margin-top: 10px">
      <el-collapse-item :title="`참고한 데이터 ${evidence.length}건`">
        <div v-for="(e, i) in evidence" :key="i" class="muted">• {{ TOOL[e.source] || e.source }} · {{ e.ref }}</div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>
