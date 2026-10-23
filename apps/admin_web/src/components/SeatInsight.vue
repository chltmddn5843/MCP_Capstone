<script setup>
// 자리 하나의 '왜 확인이 필요한가 → 해결책 선택지 → AI 분석'. 이유·선택지는 insight.js 규칙으로 즉시 나온다.
// 선택지마다 지금 할 수 있는 실행 버튼이 붙는다: 사용 의사 확인 요청(POST /confirmations), 이용권 회수 처리 요청(승인 대기), 다른 화면 링크.
// 본인 Slack 안내는 경보 배치가 이미 보낸 것이라 상태만 보여 준다. AI 분석은 버튼을 눌렀을 때만 에이전트(analyze_seat_usage)를
// 이 패널 안에서 돌리고, 같은 세션 안에서 사람·날짜별로 기억해 다시 눌러도 재호출하지 않는다.
import { ref, computed, watch } from 'vue'
import { createTask, errorLabel } from '../request.js'
import { requestConfirmation, createReclaimPlan } from '../api.js'
import { seatInsight } from '../insight.js'
import TaskStream from './TaskStream.vue'
import Md from './Md.vue'

const props = defineProps({
  employee: { type: Object, required: true }, // { id, name }
  pace: { type: Object, default: null },
  detail: { type: Object, default: null },
  tools: { type: Array, default: () => [] },
  status: { type: String, default: 'active' },
  models: { type: Array, default: () => [] },
  alertAt: { type: String, default: '' }, // 본인 Slack 경보가 나간 시각 (GET /anomalies status=open)
})
const emit = defineEmits(['changed'])
const CACHE = new Map() // `${employee_id}:${YYYY-MM-DD}` → { answer, evidence, at }
const key = () => `${props.employee.id}:${new Date().toISOString().slice(0, 10)}`
const insight = computed(() => seatInsight(props))
const cached = ref(CACHE.get(key()) ?? null)
const taskId = ref(''), err = ref(''), busy = ref(false)
const note = ref({ text: '', err: false, to: '' })
const acting = ref('')
watch(() => props.employee.id, () => { cached.value = CACHE.get(key()) ?? null; taskId.value = ''; err.value = ''; note.value = { text: '', err: false, to: '' } })

const time = (s) => (s ? new Date(s).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : '')
const BTN = { confirm: '확인 요청 보내기', reclaim: '회수 요청 만들기', ai: 'AI로 분석' }

async function run() {
  if (busy.value) return
  busy.value = true; err.value = ''; cached.value = null
  try {
    const c = await createTask(`${props.employee.name} 님이 오늘 토큰을 많이 쓰는 이유를 분석하고 다른 모델을 추천해줘`, { promptName: 'analyze_seat_usage', promptArgs: { employee_id: props.employee.id } })
    taskId.value = c.task_id
  } catch (e) { err.value = errorLabel(e) }
  busy.value = false
}
// 관리자 채널 답에는 '근거:' 줄(도구 이름·식별자)이 붙는다. 본문과 떼어 접어 둔다
function onDone(ev) {
  const [answer, ...rest] = String(ev.result.answer ?? '').split(/\n+근거:\s*/)
  const v = { answer: answer.trim(), evidence: rest.join(' ').trim(), at: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) }
  CACHE.set(key(), v); cached.value = v; taskId.value = ''
}
function onFailed(ev) { err.value = ev.error ?? errorLabel(ev); taskId.value = '' }

// 선택지 실행. 처리 요청을 만든 것은 승인 대기로 안내하고 부모가 목록을 다시 읽게 한다
async function act(f) {
  const a = f.action
  if (a.kind === 'ai') { run(); return }
  if (acting.value) return
  acting.value = f.text; note.value = { text: '', err: false, to: '' }
  try {
    if (a.kind === 'confirm') {
      await requestConfirmation(props.employee.id)
      note.value = { text: `${props.employee.name} 님에게 ${a.product} 사용 의사 확인을 요청했어요. 회수 요청은 승인 대기에 올라가 있고, 답이 오기 전에는 회수하지 않아요.`, err: false, to: '/inbox' }
    } else if (a.kind === 'reclaim') {
      const id = await createReclaimPlan(props.employee.id, a.toolId, `${props.status === 'resigned' ? '퇴사' : '휴직'} 직원 ${a.product} 이용권 회수`)
      note.value = { text: `${a.product} 회수 요청을 만들었어요. 관리자 승인 뒤 회수돼요.`, err: false, to: `/inbox?id=${id}` }
    }
    emit('changed')
  } catch (e) { note.value = { text: errorLabel(e), err: true, to: '' } }
  acting.value = ''
}
</script>

<template>
  <section v-if="insight.reasons.length" class="pace-box" :class="pace && `pace-${pace.level}`" aria-labelledby="why-h">
    <h3 id="why-h" class="small">왜 확인이 필요한가</h3>
    <ul class="why">
      <li v-for="r in insight.reasons" :key="r.key"><strong>{{ r.title }}</strong><span class="small">{{ r.body }}</span></li>
    </ul>

    <h3 class="small">해결책 선택지</h3>
    <ol class="choices">
      <li v-for="(f, i) in insight.fixes" :key="f.text" class="choice" :class="{ act: f.action.kind !== 'none' }">
        <span class="n">{{ i + 1 }}</span>
        <div class="choice-body">
          <span class="small">{{ f.text }}</span>
          <template v-if="f.action.kind === 'alert'">
            <span v-if="alertAt" class="xs done">✓ 본인 Slack 안내 완료 · {{ time(alertAt) }} (모델 변경 권유 + 현재 작업 분석 버튼)</span>
            <span v-else class="xs muted">2배 이상이면 5분 안에 본인 Slack으로 자동 안내돼요. 관리자가 따로 보낼 수는 없어요.</span>
          </template>
          <RouterLink v-else-if="f.action.kind === 'link'" :to="f.action.to" class="btn btn-sm">{{ f.action.label }}</RouterLink>
          <button v-else-if="f.action.kind === 'ai'" type="button" class="btn btn-sm" :class="{ 'btn-dark': pace?.level === 'over' }" :disabled="busy || !!taskId || !!cached" @click="act(f)">{{ cached ? '아래 분석 참고' : busy ? '요청 중…' : BTN.ai }}</button>
          <button v-else-if="BTN[f.action.kind]" type="button" class="btn btn-sm btn-dark" :disabled="!!acting" @click="act(f)">{{ acting === f.text ? '처리 중…' : BTN[f.action.kind] }}</button>
        </div>
      </li>
    </ol>
    <p v-if="note.text" class="status xs" :class="{ err: note.err }" :role="note.err ? 'alert' : 'status'" style="margin: 0">
      {{ note.text }} <RouterLink v-if="note.to" :to="note.to" class="note-link">승인 대기 보기</RouterLink>
    </p>

    <template v-if="pace && pace.level !== 'normal'">
      <div v-if="cached" class="inset ai">
        <span class="xs muted">AI 분석 · {{ cached.at }}</span>
        <Md :text="cached.answer" />
        <details v-if="cached.evidence" class="xs"><summary>참고한 데이터</summary><p class="xs muted" style="margin: 6px 0 0; white-space: pre-wrap">{{ cached.evidence }}</p></details>
        <button type="button" class="link-btn xs" :disabled="busy" @click="run">다시 분석</button>
      </div>
      <TaskStream v-else-if="taskId" :task-id="taskId" class="stream" @done="onDone" @failed="onFailed" />
      <p v-if="err" class="status err xs" role="alert" style="margin: 0">{{ err }}</p>
      <span class="xs muted">AI는 사용 패턴만 보고 추정해요. 대화 내용은 보지 않고, 결과는 이용권 관리에만 씁니다.</span>
    </template>
  </section>
</template>

<style scoped>
.pace-box { display: flex; flex-direction: column; gap: 8px; padding: 12px; border-radius: 10px; border: 1px solid var(--line-strong); }
.pace-box.pace-over { border: 2px solid var(--ink); background: rgba(220, 239, 109, 0.35); }
.pace-box.pace-caution { background: rgba(220, 239, 109, 0.18); }
.pace-box h3 { margin: 0; }
.why { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.why li { display: flex; flex-direction: column; gap: 2px; }
.choices { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.choice { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 10px; background: var(--white); border: 1px solid var(--line); }
.choice.act { border-color: var(--line-strong); }
.choice .n { width: 22px; height: 22px; border-radius: 999px; background: var(--ink); color: var(--lime); font-size: 12px; font-weight: 700; display: grid; place-items: center; flex: none; }
.choice-body { display: flex; flex-direction: column; gap: 6px; min-width: 0; flex: 1; line-height: 1.5; }
.choice-body .btn { align-self: flex-start; }
.done { font-weight: 600; }
.note-link { font-weight: 700; margin-left: 6px; }
.ai { gap: 6px; }
.link-btn { align-self: flex-start; min-height: 32px; padding: 0 10px; border: 1px solid var(--line-strong); border-radius: 999px; background: var(--white); }
.stream { padding: 12px; }
</style>
