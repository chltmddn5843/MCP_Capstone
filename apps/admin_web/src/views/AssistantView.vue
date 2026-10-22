<script setup>
// AI 비서: 추천 질문 + 자유 입력 + 진행 스트림. 같은 대화(thread)를 이어간다. ?q= 로 들어오면 바로 묻는다 (좌석 배치도의 '작업 분석').
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { createTask, getTasks, errorLabel } from '../request.js'
import { QUICK, TASK_STATUS } from '../labels.js'
import TaskStream from '../components/TaskStream.vue'

const route = useRoute()
const text = ref(''), newThread = ref(false), threadId = ref(null), tasks = ref([]), history = ref([]), notice = ref('')

async function ask(q, promptName, promptArgs) {
  const input = (q ?? text.value).trim()
  if (!input) return
  try {
    const c = await createTask(input, { promptName, promptArgs, threadId: newThread.value || promptName ? null : threadId.value })
    threadId.value = c.thread_id
    tasks.value.unshift({ id: c.task_id, key: c.task_id })
    text.value = ''; notice.value = ''
  } catch (e) { notice.value = errorLabel(e) }
}
async function loadHistory() { try { history.value = await getTasks(true, 10) } catch { history.value = [] } }
onMounted(() => {
  loadHistory()
  if (route.query.q) ask(String(route.query.q), route.query.prompt, route.query.employee ? { employee_id: route.query.employee } : undefined)
})
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">AI 비서 · 제품 선택·이용권·비용에 관한 요청</span><h1>AI 비서에게 묻기</h1></div>
  </header>
  <section class="card" style="gap: 12px">
    <div class="tags" style="gap: 8px">
      <button v-for="q in QUICK" :key="q" type="button" class="chip" @click="ask(q)">{{ q }}</button>
    </div>
    <form class="tags" style="gap: 8px; align-items: flex-end" @submit.prevent="ask()">
      <label class="ask-field" for="ask-input">요청 내용
        <input id="ask-input" v-model="text" class="ask-input" placeholder="예: 오늘 토큰을 많이 쓰는 좌석이 있는지 알려줘" />
      </label>
      <label class="small new-thread"><input v-model="newThread" type="checkbox" />새 대화로 시작</label>
      <button type="submit" class="btn btn-dark" :disabled="!text.trim()">보내기</button>
    </form>
    <span class="xs muted">대화: {{ threadId ?? '새 대화' }} · 대화 내용은 저장하지 않고 주제와 요약만 남깁니다.</span>
    <p v-if="notice" class="status" role="status">{{ notice }}</p>
  </section>
  <TaskStream v-for="t in tasks" :key="t.key" :task-id="t.id" @done="loadHistory" @approval="loadHistory" />
  <section class="card" aria-labelledby="hist-h">
    <h2 id="hist-h">내 요청</h2>
    <details v-for="t in history" :key="t.task_id" class="small">
      <summary>{{ t.created_at.slice(5, 16).replace('T', ' ') }} · {{ TASK_STATUS[t.status] ?? t.status }} · {{ t.input.slice(0, 60) }}</summary>
      <p v-if="t.result" style="white-space: pre-wrap; line-height: 1.6">{{ t.result.answer }}</p>
      <p v-if="t.error" style="color: #b00020">{{ t.error }}</p>
    </details>
    <p v-if="!history.length" class="small muted" style="margin: 0">아직 요청이 없습니다.</p>
  </section>
</template>

<style scoped>
.ask-field { flex: 1 1 320px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.new-thread { display: flex; align-items: center; gap: 6px; min-height: 44px; }
.ask-input { width: 100%; font-weight: 400; min-height: 44px; padding: 0 12px; border: 1px solid rgba(17, 17, 19, 0.16); border-radius: 10px; background: var(--white); font-size: 14px; }
summary { cursor: pointer; min-height: 36px; display: flex; align-items: center; }
</style>
