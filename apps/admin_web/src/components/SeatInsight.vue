<script setup>
// 자리 하나의 패널: ① 왜 확인이 필요한가(규칙) → ② AI 분석 → ③ 해결책 선택지. 토큰 경보는 ②를 거친 뒤 ③이 열리고(급하면 '분석 없이 보기'),
// 이용권 확인(장기 미사용·휴직·퇴사)은 분석할 사용 패턴이 없어 ①에서 ③으로 바로 간다. 이유·선택지는 insight.js 규칙으로 즉시 나온다.
// 선택지마다 지금 할 수 있는 실행 버튼: 사용 의사 확인 요청(POST /confirmations, 보냈으면 상태만), 이용권 회수 처리 요청(승인 대기), 다른 화면 링크.
// 본인 Slack 안내는 경보 배치가 이미 보낸 것이라 상태만. AI 분석(analyze_seat_usage)은 패널 안에서 돌리고 같은 세션 안에서 사람·날짜별로 기억한다.
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
  confirmation: { type: Object, default: null }, // getConfirmationMap()의 한 항목 { status, label, due }
})
const emit = defineEmits(['changed'])
const CACHE = new Map() // `${employee_id}:${YYYY-MM-DD}` → { answer, evidence, at }
const key = () => `${props.employee.id}:${new Date().toISOString().slice(0, 10)}`
const insight = computed(() => seatInsight(props))
const alerting = computed(() => !!props.pace && props.pace.level !== 'normal')
const cached = ref(CACHE.get(key()) ?? null)
const taskId = ref(''), err = ref(''), busy = ref(false)
const note = ref({ text: '', err: false, to: '' })
const acting = ref('')
const skip = ref(false) // '분석 없이 보기'
const open = computed(() => !alerting.value || !!cached.value || skip.value) // 선택지를 열 때
watch(() => props.employee.id, () => { cached.value = CACHE.get(key()) ?? null; taskId.value = ''; err.value = ''; skip.value = false; note.value = { text: '', err: false, to: '' } })

const time = (s) => (s ? new Date(s).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : '')
const BTN = { confirm: '확인 요청 보내기', reclaim: '회수 요청 만들기' }

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
const sent = ref(false) // 이 세션에서 방금 보낸 확인 요청 (부모가 다시 읽기 전까지)
async function act(f) {
  const a = f.action
  if (acting.value) return
  acting.value = f.text; note.value = { text: '', err: false, to: '' }
  try {
    if (a.kind === 'confirm') {
      await requestConfirmation(props.employee.id)
      sent.value = true
      note.value = { text: `${props.employee.name} 님에게 ${a.product} 사용 의사 확인을 요청했어요. 회수 요청은 승인 대기에 올라가 있고, 5영업일 안에 답이 없으면 자동 회수 대상이 돼요.`, err: false, to: '/inbox' }
    } else if (a.kind === 'reclaim') {
      const id = await createReclaimPlan(props.employee.id, a.toolId, `${props.status === 'resigned' ? '퇴사' : '휴직'} 직원 ${a.product} 이용권 회수`)
      note.value = { text: `${a.product} 회수 요청을 만들었어요. 관리자 승인 뒤 회수돼요.`, err: false, to: `/inbox?id=${id}` }
    }
    emit('changed')
  } catch (e) { note.value = { text: errorLabel(e), err: true, to: '' } }
  acting.value = ''
}
watch(() => props.employee.id, () => { sent.value = false })
const cfmState = computed(() => (sent.value ? { status: 'pending', label: '보냄 · 방금' } : props.confirmation))
</script>

<template>
  <section v-if="insight.reasons.length" class="pace-box" :class="pace && `pace-${pace.level}`" aria-labelledby="why-h">
    <h3 id="why-h" class="small">① 왜 확인이 필요한가</h3>
    <ul class="why">
      <li v-for="r in insight.reasons" :key="r.key">
        <strong>{{ r.title }}</strong><span class="small">{{ r.body }}</span>
        <RouterLink v-if="r.toolId" :to="{ path: '/licenses', query: { product: r.toolId } }" class="xs link">구독·이용권에서 보기</RouterLink>
      </li>
    </ul>

    <template v-if="alerting">
      <h3 class="small">② AI 분석 <span class="xs muted">사용 패턴만 보고 추정 · 대화 내용은 보지 않음</span></h3>
      <div v-if="cached" class="inset ai">
        <span class="xs muted">분석 · {{ cached.at }}</span>
        <Md :text="cached.answer" />
        <details v-if="cached.evidence" class="xs"><summary>참고한 데이터</summary><p class="xs muted" style="margin: 6px 0 0; white-space: pre-wrap">{{ cached.evidence }}</p></details>
        <button type="button" class="link-btn xs" :disabled="busy" @click="run">다시 분석</button>
      </div>
      <TaskStream v-else-if="taskId" :task-id="taskId" class="stream" @done="onDone" @failed="onFailed" />
      <div v-else class="tags" style="gap: 8px; align-items: center">
        <button type="button" class="btn btn-sm" :class="{ 'btn-dark': pace.level === 'over' }" :disabled="busy" @click="run">{{ busy ? '요청 중…' : 'AI로 분석' }}</button>
        <button v-if="!skip" type="button" class="link-btn xs" @click="skip = true">분석 없이 해결책 보기</button>
      </div>
      <p v-if="err" class="status err xs" role="alert" style="margin: 0">{{ err }}</p>
    </template>

    <h3 class="small">{{ alerting ? '③' : '②' }} 해결책 선택지 <span v-if="!open" class="xs muted">AI 분석이 끝나면 열립니다</span></h3>
    <ol v-if="open" class="choices">
      <li v-for="(f, i) in insight.fixes" :key="f.text" class="choice" :class="{ act: f.action.kind !== 'none' }">
        <span class="n">{{ i + 1 }}</span>
        <div class="choice-body">
          <span class="small">{{ f.text }}</span>
          <template v-if="f.action.kind === 'alert'">
            <span v-if="alertAt" class="xs done">✓ 본인 Slack 안내 완료 · {{ time(alertAt) }} (점검 체크리스트 + 현재 작업 분석 버튼)</span>
            <span v-else class="xs muted">2배 이상이면 5분 안에 본인 Slack으로 자동 안내돼요. 관리자가 따로 보낼 수는 없어요.</span>
          </template>
          <RouterLink v-else-if="f.action.kind === 'link'" :to="f.action.to" class="btn btn-sm">{{ f.action.label }}</RouterLink>
          <template v-else-if="f.action.kind === 'confirm' && cfmState">
            <span v-if="cfmState.status === 'pending'" class="xs done">✓ {{ cfmState.label }} · 답을 기다리는 중</span>
            <span v-else-if="cfmState.status === 'overdue'" class="xs done">{{ cfmState.label }}</span>
            <span v-else class="xs done">{{ cfmState.label }} · 필요하면 다시 요청</span>
            <button v-if="cfmState.status === 'answered'" type="button" class="btn btn-sm" :disabled="!!acting" @click="act(f)">{{ acting === f.text ? '처리 중…' : '다시 확인 요청' }}</button>
          </template>
          <button v-else-if="BTN[f.action.kind]" type="button" class="btn btn-sm btn-dark" :disabled="!!acting" @click="act(f)">{{ acting === f.text ? '처리 중…' : BTN[f.action.kind] }}</button>
        </div>
      </li>
    </ol>
    <p v-if="note.text" class="status xs" :class="{ err: note.err }" :role="note.err ? 'alert' : 'status'" style="margin: 0">
      {{ note.text }} <RouterLink v-if="note.to" :to="note.to" class="note-link">승인 대기 보기</RouterLink>
    </p>
    <span class="xs muted">사용량은 이용권 관리에만 쓰고 인사평가에 쓰지 않습니다.</span>
  </section>
</template>

<style scoped>
.pace-box { display: flex; flex-direction: column; gap: 8px; padding: 12px; border-radius: 10px; border: 1px solid var(--line-strong); }
.pace-box.pace-over { border: 2px solid var(--ink); background: rgba(220, 239, 109, 0.35); }
.pace-box.pace-caution { background: rgba(220, 239, 109, 0.18); }
.pace-box h3 { margin: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; }
.why { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.why li { display: flex; flex-direction: column; gap: 2px; }
.link { align-self: flex-start; font-weight: 600; }
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
