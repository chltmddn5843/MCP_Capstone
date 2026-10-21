// 화면이 부르는 데이터 함수 전부. 지금은 mock.js를 돌려주고, 백엔드에 연결할 때 함수 본문만 fetch로 바꾼다.
// 각 함수 위 주석이 대응하는 REST 경로다 (apps/backend/main.py, 응답은 Envelope{data}). 화면 모양 ↔ 스키마 변환도 여기서 한다.
import * as db from './mock.js'

const copy = (v) => Promise.resolve(structuredClone(v))
const find = (id) => db.plans.find((p) => p.id === id)

// 연결 예시: export const getMe = () => request('/me')
// async function request(path, init) {
//   const res = await fetch(`/api${path}`, { ...init, headers: { 'content-type': 'application/json', Authorization: `Bearer ${localStorage.token}` } })
//   const body = await res.json()
//   if (!res.ok) throw new Error(body.error?.message ?? res.statusText)
//   return body.data
// }

// GET /me
export const getMe = () => copy(db.me)
// GET /usage + GET /savings + GET /inventory 합계
export const getSummary = () => copy(db.summary)
// GET /inventory
export const getProducts = () => copy(db.products)
// GET /plans?type=seat_assign
export const getSeatRequests = () => copy(db.seatRequests)
// GET /anomalies, GET /anomalies/{id}
export const getAnomalies = () => copy(db.anomalies)
// GET /usage?group_by=project
export const getProjects = () => copy(db.projects)
// GET /plans
export const getPlans = () => copy(db.plans)
// GET /updates + GET /review-runs (v2 신규)
export const getUpdates = () => copy(db.updates)
export const getSuggestionStats = () => copy(db.suggestionStats)
// GET /departments (v2 신규)
export const getTeamSwitches = () => copy(db.teamSwitches)
// GET /unmet-needs
export const getUnmetNeeds = () => copy(db.unmetNeeds)
// GET /adoption/teams
export const getTeamAdoption = () => copy(db.teamAdoption)

// 사이드바 배지
export const getCounts = () => Promise.resolve({
  inbox: db.plans.filter((p) => p.status === 'pending_approval').length,
  cost: db.anomalies.filter((a) => a.status === 'open').length,
})

// POST /confirmations
export function requestConfirmation(seatId) {
  for (const p of db.products) {
    const s = p.seats.find((x) => x.id === seatId)
    if (s) { s.confirmation = '응답 대기 · 기한 5영업일'; s.action = 'remind' }
  }
  return Promise.resolve()
}

// POST /plans — 비용 급증 알림의 대응 선택으로 처리 요청을 만든다
export function createPlanFromAnomaly(anomalyId, actionId) {
  const a = db.anomalies.find((x) => x.id === anomalyId)
  const action = a.investigation.actions.find((x) => x.id === actionId)
  const id = `PLN-${String(150 + db.plans.length).padStart(4, '0')}`
  db.plans.unshift({
    id, type: 'budget_review', risk: 'medium', status: 'pending_approval', createdAt: '방금',
    title: action.label, subtitle: `${a.scopeName} · 비용 급증 알림 대응`, requester: '광철 (관리자)',
    summary: `${a.scopeName} 프로젝트 비용 급증(${a.ratio}배)에 대한 대응 요청입니다.`,
    steps: [{ label: '요청 작성', at: '방금', done: true }, { label: '관리자 승인', at: '지금 단계', current: true }, { label: '실행·안내', at: '승인 후' }],
    aiOpinion: { title: '조사 결과 첨부', body: a.investigation.causes.map((c) => c.title).join(' · ') },
    changes: [['프로젝트', a.scopeName], ['대응', action.label]],
    evidence: a.investigation.evidence,
  })
  a.status = 'investigating'
  return Promise.resolve(id)
}

// POST /plans/{id}/approve → POST /plans/{id}/execute (실행 직전 서버가 상태를 다시 확인한다)
export function approvePlan(id) {
  const p = find(id)
  p.status = p.risk === 'high' ? 'approved' : 'executed'
  return Promise.resolve(p.status)
}
// POST /plans/{id}/reject
export function rejectPlan(id) {
  find(id).status = 'rejected'
  return Promise.resolve()
}
// PATCH /departments/{id} (v2 신규)
export function setTeamSwitch(id, enabled) {
  db.teamSwitches.find((t) => t.id === id).enabled = enabled
  return Promise.resolve()
}
