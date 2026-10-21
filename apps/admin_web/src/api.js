// 화면이 부르는 데이터 함수 전부. 백엔드 응답(Envelope{data}, packages/schemas)을 화면 모양으로 바꾼다. 화면은 이 파일만 본다.
// 함수 이름과 반환 모양은 목업 시절과 같다 (화면 수정 없이 연결). 변환 규칙은 각 함수 주석.
import { get, post, request } from './request.js'
import { PLAN_TYPE, BILLING, TOOL_LABEL, cap } from './labels.js'

const dt = (s) => (s ? s.slice(5, 16).replace('T', ' ') : '')
const daysAgo = (s) => (s ? `${Math.max(0, Math.round((Date.now() - new Date(s)) / 86400000))}일 전` : '기록 없음')
const ym = (d) => `${d.getMonth() + 1}월`

// GET /me
export async function getMe() {
  const m = await get('/me')
  const e = m.employee
  return { name: e.name, role: `${e.role === 'admin' ? '관리자' : '직원'} · ${e.job_title}`, employee: e }
}

// GET /inventory → 제품 목록 (좌석형) + GET /tools (API형 제품)
export async function getProducts() {
  const [inv, tools] = await Promise.all([get('/inventory'), get('/tools')])
  const seatProducts = inv.map((i) => ({
    id: i.contract.tool_id, name: i.tool_name, plan: i.contract.plan_name, kind: (tools.find((t) => t.id === i.contract.tool_id)?.kind === 'software') ? '일반 소프트웨어' : 'AI',
    billing: BILLING[i.contract.billing_type] ?? i.contract.billing_type,
    seatsPurchased: i.purchased, seatsAssigned: i.assigned, seatPrice: i.contract.seat_price_krw, monthCost: i.assigned * i.contract.seat_price_krw,
    renewal: i.contract.term_end?.slice(0, 10),
    seats: i.low_usage_candidates.map((c) => ({
      id: c.employee_id, name: c.employee_name, dept: c.dept_name, flag: c.flag, lastUsed: daysAgo(c.last_activity_at),
      confirmation: c.needs_confirmation ? '아직 묻지 않음' : '확인 필요 없음', action: c.needs_confirmation ? 'ask' : null,
      contractId: i.contract.id,
    })),
  }))
  const apiProducts = tools.filter((t) => t.contract?.billing_type === 'api_usage').map((t) => ({
    id: t.id, name: t.product, plan: t.contract.plan_name, kind: 'AI', billing: BILLING.api_usage, seatsPurchased: 0, seatsAssigned: 0, seatPrice: 0,
    monthCost: 0, renewal: t.contract.term_end?.slice(0, 10), projects: 0, seats: [],
  }))
  return [...seatProducts, ...apiProducts]
}

// GET /plans?type=seat_assign → 이용권 신청 목록
export async function getSeatRequests() {
  const page = await get('/plans', { type: 'seat_assign' })
  return page.items.map((p) => ({
    id: p.id, who: p.requested_by, product: p.items[0]?.contract_id ?? '', purpose: p.rationale,
    status: p.status === 'pending_approval' ? 'pending' : 'done',
    note: p.status === 'executed' ? `미배정 좌석 배정 완료 · ${dt(p.executed_at)}` : p.status === 'pending_approval' ? '미배정 좌석 없음 → AI 의견과 함께 승인 대기' : (PLAN_TYPE[p.type] + ' · ' + p.status),
  }))
}

// GET /anomalies + GET /anomalies/{id} → 알림 + 추이 + 조사 틀. AI 조사 결과는 알림 상세의 project·breakdown으로 근거만 채우고, 원인 후보는 '원인 조사 실행'(에이전트)으로 받는다.
export async function getAnomalies() {
  const list = await get('/anomalies')
  return Promise.all(list.map(async (a) => {
    const d = await get(`/anomalies/${a.id}`)
    const daily = d.series.map((p) => p.cost.krw)
    const now = new Date()
    const monthToDate = d.series.filter((p) => new Date(p.period_start).getMonth() === now.getMonth()).reduce((s, p) => s + p.cost.krw, 0)
    return {
      id: a.id, status: a.status, scopeName: a.scope_name ?? a.scope_id, product: d.project?.model_id ? 'AI-B API' : '', model: d.project?.model_id ?? '', env: d.project?.environment === 'prod' ? '운영' : '테스트', dept: d.project?.dept_id ?? '',
      detectedAt: dt(a.created_at), baseline: Math.round(a.baseline), observed: Math.round(a.observed), ratio: a.ratio, projected: a.projected_monthly_cost?.krw ?? 0,
      budget: d.project?.monthly_budget_krw ?? 0, monthToDate, daily, dailyStart: d.series[0]?.period_start?.slice(5, 10).replace('-', '/') ?? '',
      projectId: d.project?.id, purpose: d.project?.purpose,
      investigation: {
        doneAt: null, causes: [],
        evidence: ['프로젝트 등록 목적·예산', ...d.breakdown_by_model.map((b) => `모델 ${b.key} ${Math.round(b.share * 100)}%`), ...d.breakdown_by_input_length.map((b) => `입력 ${b.key} ${Math.round(b.share * 100)}%`)],
        actions: [
          { id: 'repeat_check', label: '반복 요청 점검 · 부서 확인 요청' },
          { id: 'budget_review', label: '예산 검토' },
          { id: 'model_review', label: '품질 평가 후 모델 검토' },
        ],
      },
    }
  }))
}

// 프로젝트 목록: 백엔드에 GET /projects 가 없어 알림 상세에서 아는 프로젝트만 보인다 (백엔드 요청 항목).
export async function getProjects() {
  const anomalies = await getAnomalies()
  return anomalies.filter((a) => a.projectId).map((a) => ({ id: a.projectId, name: a.scopeName, dept: a.dept, model: a.model, env: a.env, cost: a.monthToDate, budget: a.budget, anomaly: a.status === 'open' }))
}

// GET /inventory + /savings + /usage → 홈 요약. 월별 추이는 계약 사용량 60일을 주 단위로 묶는다 (월 단위 API 없음).
export async function getSummary() {
  const [inv, savings, products] = await Promise.all([get('/inventory'), get('/savings').catch(() => ({ by_kind: {}, total_krw: 0 })), getProducts()])
  const seatsTotal = inv.reduce((s, i) => s + i.purchased, 0), seatsAssigned = inv.reduce((s, i) => s + i.assigned, 0)
  const seatsToCheck = inv.reduce((s, i) => s + i.low_usage_candidates.filter((c) => c.needs_confirmation).length, 0)
  const monthCost = products.reduce((s, p) => s + (p.monthCost || 0), 0)
  let monthly = []
  if (inv[0]) {
    const end = new Date(), start = new Date(end.getTime() - 42 * 86400000)
    const u = await get('/usage', { scope: 'contract', scope_id: inv[0].contract.id, start: start.toISOString(), end: end.toISOString() }).catch(() => null)
    if (u) {
      const buckets = new Map()
      for (const p of u.series) { const d = new Date(p.period_start); const key = `${d.getMonth() + 1}/${Math.ceil(d.getDate() / 7)}주`; buckets.set(key, (buckets.get(key) || 0) + p.cost.krw) }
      monthly = [...buckets.entries()].slice(-6).map(([label, value]) => ({ label, value }))
    }
  }
  return { monthCost, monthBudget: Math.round(monthCost * 1.08), seatsAssigned, seatsTotal, seatsToCheck, savingsMonth: savings.total_krw,
    savingsNote: Object.entries(savings.by_kind).map(([k, v]) => `${k === 'purchase_avoided' ? '아낀 구매 비용' : k} ${Math.round(v).toLocaleString('ko-KR')}원`).join(' · ') || '기록 없음',
    monthly: monthly.length ? monthly : [{ label: ym(new Date()), value: monthCost }] }
}

// GET /plans → 승인 대기·이력. steps는 상태에서 만들고, AI 의견은 ai_opinion(없으면 요청 사유)에서 만든다.
const PLAN_STEPS = (p) => {
  const base = [{ label: '요청 접수', at: dt(p.created_at), done: true }]
  if (p.ai_opinion) base.push({ label: 'AI 의견', at: '첨부됨', done: true })
  if (p.status === 'pending_approval') base.push({ label: p.risk_level === 'high' ? '책임자 결정' : '관리자 승인', at: '지금 단계', current: true }, { label: '실행·안내', at: '승인 후' })
  else if (p.status === 'approved') base.push({ label: '관리자 승인', at: dt(p.approved_at), done: true }, { label: '실행·안내', at: '실행 전', current: true })
  else if (p.status === 'executed') base.push({ label: '관리자 승인', at: dt(p.approved_at) || '자동', done: true }, { label: '실행·안내', at: dt(p.executed_at), done: true })
  else if (p.status === 'rejected') base.push({ label: '반려', at: p.reject_reason ?? '', done: true })
  return base
}
const KEY_KO = { employee_id: '직원', contract_id: '계약', project_id: '프로젝트', from_model_id: '현재 모델', to_model_id: '변경 모델', environment: '환경', confirmation_id: '사용 의사 응답', reassign_to_employee_id: '재배정 대상', tool_id: '제품', quantity: '수량', current_budget_krw: '현재 예산', proposed_budget_krw: '제안 예산', note: '메모', capability_tag: '필요 기능' }
export async function getPlans() {
  const page = await get('/plans', { limit: 100 })
  return page.items.map((p) => ({
    id: p.id, type: p.type, risk: p.risk_level, status: p.status, createdAt: dt(p.created_at),
    title: PLAN_TYPE[p.type] ?? p.type, subtitle: Object.values(p.items[0] ?? {}).filter((v) => typeof v === 'string').slice(0, 3).join(' · '),
    requester: p.requested_by, summary: p.rationale, steps: PLAN_STEPS(p),
    aiOpinion: p.ai_opinion ? { title: 'AI 의견', body: p.ai_opinion } : { title: '요청 사유', body: p.rationale },
    changes: Object.entries(p.items[0] ?? {}).map(([k, v]) => [KEY_KO[k] ?? k, String(v)]),
    evidence: (p.evidence ?? []).map((e) => `${TOOL_LABEL[e.source] ?? e.source} · ${e.ref}`),
    raw: p,
  }))
}

// GET /updates + GET /suggestions → 업데이트별 판단 (팀별 결과는 제안 기록에서)
export async function getUpdates() {
  const [upd, sugg] = await Promise.all([get('/updates'), get('/suggestions', { limit: 200 })])
  const byUpdate = (id) => (sugg.items ?? sugg).filter((s) => s.update_id === id)
  return upd.items.map((u) => {
    const ss = byUpdate(u.id)
    const anySent = ss.some((s) => s.status === 'sent' || s.status === 'draft' || s.status === 'pending_approval')
    const hold = ss.find((s) => s.status === 'on_hold')
    return {
      id: u.id, product: u.vendor, date: u.published_at.slice(5, 10).replace('-', '/'), title: u.title, sourceUrl: u.url,
      result: anySent ? 'sent' : 'held', note: !ss.length ? '아직 검토하지 않음' : hold && !anySent ? `전체 보류 · ${hold.hold_reason}` : undefined,
      teams: ss.filter((s) => s.status !== 'on_hold' || s.target_id).map((s) => ({
        team: s.target_id ?? '전사', result: s.status === 'sent' ? 'sent' : s.status === 'on_hold' ? 'held' : 'sent', at: s.sent_at ? dt(s.sent_at) : undefined,
        reason: s.status === 'on_hold' ? s.hold_reason : s.relevance, reaction: undefined,
      })),
    }
  })
}
export async function getSuggestionStats() {
  const [upd, sugg, teams] = await Promise.all([get('/updates'), get('/suggestions', { limit: 200 }), get('/adoption/teams').catch(() => [])])
  const items = sugg.items ?? sugg
  const useful = teams.reduce((s, t) => s + t.useful, 0), irrelevant = teams.reduce((s, t) => s + t.irrelevant, 0)
  return { collected: upd.total ?? upd.items.length, sent: items.filter((s) => s.status === 'sent').length, held: items.filter((s) => s.status === 'on_hold').length,
    helpfulRate: useful + irrelevant ? Math.round((useful / (useful + irrelevant)) * 100) : 0, nextRun: '주 1회' }
}
// 팀별 발송 스위치: 백엔드에 GET/PATCH /departments 가 아직 없다 (백엔드 요청 항목). 팀 목록만 활용 현황에서 가져온다.
export async function getTeamSwitches() {
  const teams = await get('/adoption/teams').catch(() => [])
  return teams.map((t) => ({ id: t.team_id, team: t.team_name, channel: '', enabled: true, readonly: true }))
}
export function setTeamSwitch() { return Promise.resolve() }

// GET /unmet-needs
export async function getUnmetNeeds() {
  const rows = await get('/unmet-needs')
  return rows.map((n) => ({ capability: cap(n.capability_tag), count: n.count, depts: Array.from({ length: n.dept_count }, (_, i) => `부서 ${i + 1}`), deptCount: n.dept_count,
    example: n.sample_summaries[0] ?? '', thresholdMet: n.threshold_met }))
}
// GET /adoption/teams
export async function getTeamAdoption() {
  const rows = await get('/adoption/teams')
  return rows.map((t) => ({ team: t.team_name, rate: Math.round(t.active_ratio * 100), seats: t.headcount }))
}

// 사이드바 배지
export async function getCounts() {
  const [plans, anomalies] = await Promise.all([get('/plans', { status: 'pending_approval' }).catch(() => ({ items: [] })), get('/anomalies', { status: 'open' }).catch(() => [])])
  return { inbox: plans.items.length, cost: anomalies.length }
}

// POST /confirmations — 사용 의사 확인 요청. 백엔드가 plan_id를 요구하므로 그 직원의 회수 요청이 있으면 그것을, 없으면 먼저 회수 요청(승인 대기)을 만든다.
export async function requestConfirmation(employeeId) {
  const plans = await get('/plans', { type: 'seat_reclaim' })
  let plan = plans.items.find((p) => p.items[0]?.employee_id === employeeId && p.status === 'pending_approval')
  if (!plan) {
    const inv = await get('/inventory')
    const contract = inv.find((i) => i.low_usage_candidates.some((c) => c.employee_id === employeeId))?.contract.id
    plan = await post('/plans', { type: 'seat_reclaim', items: [{ employee_id: employeeId, contract_id: contract }], rationale: '장기 미사용 이용권 사용 의사 확인', evidence: [{ source: 'get_license_inventory', ref: contract }] })
  }
  return post('/confirmations', { employee_id: employeeId, plan_id: plan.id, question: '이용권을 계속 사용하시나요?' })
}

// POST /plans — 비용 급증 알림 대응 → 처리 요청
export async function createPlanFromAnomaly(anomalyId, actionId) {
  const a = (await getAnomalies()).find((x) => x.id === anomalyId)
  const label = a.investigation.actions.find((x) => x.id === actionId)?.label ?? actionId
  const plan = await post('/plans', { type: 'budget_review', items: [{ project_id: a.projectId, current_budget_krw: a.budget, note: label }], rationale: `${a.scopeName} 비용 급증(${a.ratio}배) 대응: ${label}`, evidence: [{ source: 'get_anomaly_detail', ref: anomalyId }] })
  return plan.id
}

// POST /plans/{id}/approve → (책임자 결정이 아니면) POST /plans/{id}/execute
export async function approvePlan(id, reason = '관리자 승인') {
  const p = await post(`/plans/${id}/approve`, { reason })
  if (p.risk_level === 'high') return p.status
  const r = await request(`/plans/${id}/execute`, { method: 'POST', headers: { 'Idempotency-Key': `ui_${id}_${Date.now()}` } })
  return r.plan.status
}
export async function rejectPlan(id, reason = '관리자 반려') {
  await post(`/plans/${id}/reject`, { reason })
  return 'rejected'
}
