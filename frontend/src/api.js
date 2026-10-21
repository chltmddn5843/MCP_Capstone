// 백엔드·에이전트 호출. 브라우저는 /api/* 만 부른다 (nginx 또는 Vite 프록시가 백엔드·에이전트로 나눈다).
import { useAuth } from './stores/auth'
import { ERROR_CODE } from './labels'

export class ApiError extends Error {
  constructor(code, message, status) { super(message); this.code = code; this.status = status }
  get label() { return ERROR_CODE[this.code] || this.code }
}

function headers(extra = {}) {
  const auth = useAuth()
  return { 'Content-Type': 'application/json', ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}), ...extra }
}

export async function api(method, path, { body, query, headers: extra } = {}) {
  const qs = query ? '?' + new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([, v]) => v != null && v !== ''))) : ''
  let r
  try {
    r = await fetch(`/api${path}${qs}`, { method, headers: headers(extra), body: body ? JSON.stringify(body) : undefined })
  } catch (e) {
    throw new ApiError('network', `서버에 연결할 수 없습니다 (${e.message})`, 0)
  }
  let data
  try { data = await r.json() } catch { throw new ApiError('internal', `서버가 JSON이 아닌 응답을 보냈습니다 (HTTP ${r.status})`, r.status) }
  if (data.error) throw new ApiError(data.error.code, data.error.message, r.status)
  if (!('data' in data)) throw new ApiError(r.status === 404 ? 'not_found' : 'internal', JSON.stringify(data.detail ?? data).slice(0, 200), r.status)
  return data.data
}

export const get = (path, query) => api('GET', path, { query })
export const post = (path, body, extra) => api('POST', path, { body, headers: extra })
export const patch = (path, body) => api('PATCH', path, { body })

/** SSE(text/event-stream)를 fetch로 읽어 이벤트마다 onEvent(event) 호출. 서버가 종료 이벤트에서 닫는다. */
export async function streamTask(taskId, after, onEvent, signal) {
  const r = await fetch(`/api/ai/tasks/${taskId}/stream?after=${after || 0}`, { headers: headers(), signal })
  if (!r.ok) {
    let msg = `HTTP ${r.status}`
    try { const j = await r.json(); msg = j.error?.message || msg } catch {}
    throw new ApiError('internal', `진행 상황을 받을 수 없습니다: ${msg}`, r.status)
  }
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true }).replace(/\r\n/g, '\n')  // sse-starlette는 CRLF
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2)
      const dataLine = chunk.split('\n').find(l => l.startsWith('data:'))
      if (dataLine) onEvent(JSON.parse(dataLine.slice(5)))
    }
  }
}
