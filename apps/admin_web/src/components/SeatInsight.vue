<script setup>
// 자리 하나의 '왜 확인이 필요한가 → 이렇게 해 보세요 → AI 분석'. 이유·해결책은 insight.js 규칙으로 즉시, AI 분석은 버튼을 눌렀을 때만
// 에이전트(analyze_seat_usage)를 이 패널 안에서 돌린다. 결과는 같은 세션 안에서 사람·날짜별로 기억해 다시 눌러도 재호출하지 않는다.
import { ref, computed, watch } from 'vue'
import { createTask, errorLabel } from '../request.js'
import { seatInsight } from '../insight.js'
import TaskStream from './TaskStream.vue'

const props = defineProps({
  employee: { type: Object, required: true }, // { id, name }
  pace: { type: Object, default: null },
  detail: { type: Object, default: null },
  tools: { type: Array, default: () => [] },
  status: { type: String, default: 'active' },
  models: { type: Array, default: () => [] },
})
const CACHE = new Map() // `${employee_id}:${YYYY-MM-DD}` → { answer, at }
const key = () => `${props.employee.id}:${new Date().toISOString().slice(0, 10)}`
const insight = computed(() => seatInsight(props))
const cached = ref(CACHE.get(key()) ?? null)
const taskId = ref(''), err = ref(''), busy = ref(false)
watch(() => props.employee.id, () => { cached.value = CACHE.get(key()) ?? null; taskId.value = ''; err.value = '' })

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
</script>

<template>
  <section v-if="insight.reasons.length" class="pace-box" :class="pace && `pace-${pace.level}`" aria-labelledby="why-h">
    <h3 id="why-h" class="small">왜 확인이 필요한가</h3>
    <ul class="why">
      <li v-for="r in insight.reasons" :key="r.key"><strong>{{ r.title }}</strong><span class="small">{{ r.body }}</span></li>
    </ul>
    <h3 class="small">이렇게 해 보세요</h3>
    <ol class="how small">
      <li v-for="f in insight.fixes" :key="f">{{ f }}</li>
    </ol>
    <template v-if="pace">
      <div v-if="cached" class="inset ai">
        <span class="xs muted">AI 분석 · {{ cached.at }}</span>
        <p class="answer">{{ cached.answer }}</p>
        <details v-if="cached.evidence" class="xs"><summary>참고한 데이터</summary><p class="answer xs muted" style="margin: 6px 0 0">{{ cached.evidence }}</p></details>
        <button type="button" class="link-btn xs" :disabled="busy" @click="run">다시 분석</button>
      </div>
      <TaskStream v-else-if="taskId" :task-id="taskId" class="stream" @done="onDone" @failed="onFailed" />
      <button v-else type="button" class="btn btn-sm" :class="{ 'btn-dark': pace.level === 'over' }" :disabled="busy" @click="run">{{ busy ? '요청 중…' : 'AI로 현재 작업 분석' }}</button>
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
.how { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; line-height: 1.5; }
.ai { gap: 6px; }
.answer { margin: 0; white-space: pre-wrap; line-height: 1.6; font-size: 14px; }
.link-btn { align-self: flex-start; min-height: 32px; padding: 0 10px; border: 1px solid var(--line-strong); border-radius: 999px; background: var(--white); }
.stream { padding: 12px; }
.btn { align-self: flex-start; }
</style>
