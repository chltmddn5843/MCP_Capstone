<script setup>
// 역할별 추천 질문 + 자유 입력 + 진행 스트림. 같은 대화(thread)를 이어간다.
import { ref } from 'vue'
import { post, ApiError } from '../api'
import { QUICK } from '../labels'
import { useAuth } from '../stores/auth'
import TaskStream from './TaskStream.vue'
import { ElMessage } from 'element-plus'

const auth = useAuth()
const text = ref(''), newThread = ref(false), threadId = ref(null), tasks = ref([])
defineExpose({ ask })

async function ask(q, promptName, promptArgs) {
  const input = (q ?? text.value).trim()
  if (!input) return
  try {
    const created = await post('/ai/tasks', { input, prompt_name: promptName || null, prompt_args: promptArgs || {}, thread_id: newThread.value || promptName ? null : threadId.value, channel: 'admin_ui' })
    threadId.value = created.thread_id
    tasks.value.unshift({ id: created.task_id, key: created.task_id + Date.now() })
    text.value = ''
  } catch (e) { ElMessage.error(e instanceof ApiError ? `${e.label}: ${e.message}` : String(e)) }
}
</script>

<template>
  <div>
    <div class="row" style="margin-bottom: 10px">
      <el-button v-for="q in QUICK[auth.role] || []" :key="q" size="small" @click="ask(q)">{{ q }}</el-button>
    </div>
    <div class="row" style="margin-bottom: 12px">
      <el-input v-model="text" placeholder="업무를 설명하거나 요청을 적어 주세요" style="flex: 1; min-width: 320px" @keyup.enter="ask()" />
      <el-checkbox v-model="newThread">새 대화</el-checkbox>
      <el-button type="primary" @click="ask()">보내기</el-button>
    </div>
    <div class="muted" style="margin-bottom: 8px">대화: {{ threadId || '새 대화' }}</div>
    <TaskStream v-for="t in tasks" :key="t.key" :task-id="t.id" />
  </div>
</template>
