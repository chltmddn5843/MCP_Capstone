// 백엔드 호출 공통. 브라우저는 /api/* 만 부른다 (Vite 프록시 또는 nginx가 백엔드·에이전트로 나눈다).
// 토큰은 localStorage.token (POST /auth/login으로 받은 JWT). 없거나 만료(401)면 /login으로 보낸다.

export class ApiError extends Error {
  constructor(code, message, status) { super(message); this.code = code; this.status = status }
}

const LABEL = { unauthorized: '로그인이 필요합니다', forbidden: '권한이 없습니다', not_found: '찾을 수 없습니다', invalid: '입력이 올바르지 않습니다',
  conflict: '현재 상태에서는 할 수 없습니다', stale: '승인 뒤 상황이 바뀌어 처리를 멈췄습니다', agent_unavailable: 'AI 비서 서버가 응답하지 않습니다', network: '서버에 연결할 수 없습니다' }
export const errorLabel = (e) => (e instanceof ApiError ? `${LABEL[e.code] ?? e.code}: ${e.message}` : String(e))

// 로그인: POST /auth/login (사번·이메일 + 비밀번호) → JWT. 토큰은 localStorage.token, 1시간 뒤 만료되면 401 → 로그인 화면.
async function auth(path, payload) {
  let res
  try {
    res = await fetch(`/api${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) })
  } catch (e) { throw new ApiError('network', e.message, 0) }
  const body = await res.json().catch(() => ({}))
  if (body.error) throw new ApiError(body.error.code, body.error.message, res.status)
  if (!body.data) throw new ApiError('internal', `로그인 응답을 읽을 수 없습니다 (HTTP ${res.status})`, res.status)
  localStorage.token = body.data.access_token
  localStorage.me = JSON.stringify(body.data.employee)
  return body.data.employee
}
export const login = (loginId, password) => auth('/auth/login', { login_id: loginId, password })
/** 개발 서버(npm run dev)에서만 쓰는 빠른 로그인. 백엔드가 APP_ENV=prod면 거절한다. */
export const devLogin = (employeeId) => auth('/auth/dev-login', { employee_id: employeeId })

export function logout() { localStorage.removeItem('token'); localStorage.removeItem('me') }
export const loggedIn = () => !!localStorage.token

function toLogin() {
  logout()
  if (location.pathname !== '/login') location.assign(`/login?next=${encodeURIComponent(location.pathname + location.search)}`)
}

export function ensureToken() {
  if (localStorage.token) return localStorage.token
  toLogin()
  throw new ApiError('unauthorized', '로그인이 필요합니다', 401)
}

export async function request(path, { method = 'GET', body, query, headers = {} } = {}) {
  ensureToken()
  const qs = query ? '?' + new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([, v]) => v != null && v !== ''))) : ''
  let res
  try {
    res = await fetch(`/api${path}${qs}`, { method, headers: { 'content-type': 'application/json', Authorization: `Bearer ${localStorage.token}`, ...headers }, body: body ? JSON.stringify(body) : undefined })
  } catch (e) { throw new ApiError('network', e.message, 0) }
  let data
  try { data = await res.json() } catch { throw new ApiError('internal', `서버가 JSON이 아닌 응답을 보냈습니다 (HTTP ${res.status})`, res.status) }
  if (data.error) {
    if (res.status === 401) toLogin()
    throw new ApiError(data.error.code, data.error.message, res.status)
  }
  if (!('data' in data)) throw new ApiError(res.status === 404 ? 'not_found' : 'internal', JSON.stringify(data.detail ?? data).slice(0, 200), res.status)
  return data.data
}

export const get = (path, query) => request(path, { query })
export const post = (path, body, headers) => request(path, { method: 'POST', body, headers })

/** 에이전트 진행 이벤트(SSE)를 fetch 스트리밍으로 읽는다. 서버가 종료 이벤트(DONE·FAILED·APPROVAL_REQUIRED)에서 닫는다. */
export async function streamTask(taskId, after, onEvent, signal) {
  ensureToken()
  const res = await fetch(`/api/ai/tasks/${taskId}/stream?after=${after || 0}`, { headers: { Authorization: `Bearer ${localStorage.token}` }, signal })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { msg = (await res.json()).error?.message || msg } catch {}
    throw new ApiError('internal', `진행 상황을 받을 수 없습니다: ${msg}`, res.status)
  }
  const reader = res.body.getReader(), dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true }).replace(/\r\n/g, '\n') // sse-starlette는 CRLF
    let i
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2)
      const line = chunk.split('\n').find((l) => l.startsWith('data:'))
      if (line) onEvent(JSON.parse(line.slice(5)))
    }
  }
}

// 에이전트 작업
export const createTask = (input, { promptName, promptArgs, threadId } = {}) =>
  post('/ai/tasks', { input, prompt_name: promptName ?? null, prompt_args: promptArgs ?? {}, thread_id: threadId ?? null, channel: 'admin_ui' })
export const getTasks = (mine = false, limit = 50) => get('/ai/tasks', { mine, limit })
export const approveTask = (taskId, approved, reason) => post(`/ai/tasks/${taskId}/approval`, { approved, reason })
