const API = '/api'
const TOKEN_KEY = 'partflow.admin.token'
const EMPLOYEE_ID = 'emp_asset_01'

const token = () => localStorage.getItem(TOKEN_KEY)

async function request(path, init = {}) {
  const headers = { 'content-type': 'application/json', ...(init.headers ?? {}) }
  if (token()) headers.Authorization = `Bearer ${token()}`
  const res = await fetch(`${API}${path}`, { ...init, headers })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error?.message ?? res.statusText)
  return body.data
}

async function ensureToken() {
  if (!token()) {
    const data = await request('/auth/dev-login', {
      method: 'POST',
      body: JSON.stringify({ employee_id: EMPLOYEE_ID }),
    })
    localStorage.setItem(TOKEN_KEY, data.access_token)
    return data.employee
  }
  return (await request('/me')).employee
}

const money = (value) => value?.krw ?? 0
const dateLabel = (value) => value ? new Date(value).toLocaleDateString('ko-KR') : '-'
function mapPlan(p) {
  const labels = {
    seat_reclaim: '이용권 회수·재배정',
    seat_assign: '이용권 배정',
    model_change: '테스트 환경 모델 변경',
    budget_review: '예산 검토',
    purchase_review: '추가 구매 검토',
  }
  const itemText = p.items?.map((item) => Object.values(item).filter(Boolean).join(' · ')).join(', ')
  return {
    ...p,
    risk: p.risk_level,
    createdAt: dateLabel(p.created_at),
    title: labels[p.type] ?? p.type,
    subtitle: itemText || p.type,
    requester: p.requested_by,
    summary: p.rationale,
    steps: [{ label: '요청 접수', at: dateLabel(p.created_at), done: true },
      { label: p.status === 'pending_approval' ? '관리자 승인' : '처리 결과', at: PLAN_STATUS[p.status] ?? p.status, current: p.status === 'pending_approval' }],
    aiOpinion: { title: '백엔드 처리 요청', body: p.rationale },
    changes: p.items?.map((item) => ['요청 내용', Object.values(item).filter(Boolean).join(' · ')]) ?? [],
    evidence: p.evidence?.map((e) => e.ref ?? e.source ?? JSON.stringify(e)) ?? [],
  }
}

const PLAN_STATUS = {
  pending_approval: '승인 대기', approved: '승인됨', executed: '처리 완료', rejected: '반려',
}

function mapInventory(row) {
  const seats = row.low_usage_candidates.map((s) => ({
    id: s.employee_id,
    employeeId: s.employee_id,
    name: s.employee_name,
    dept: s.dept_name,
    flag: s.flag,
    lastUsed: s.last_activity_at ? dateLabel(s.last_activity_at) : '기록 없음',
    confirmation: s.needs_confirmation ? '아직 묻지 않음' : '확인 필요 없음',
    action: s.needs_confirmation ? 'ask' : null,
  }))
  return {
    id: row.contract.id,
    name: row.tool_name,
    plan: row.contract.plan_name,
    kind: row.contract.billing_type,
    billing: row.contract.billing_type,
    seatsPurchased: row.purchased,
    seatsAssigned: row.assigned,
    seatPrice: row.contract.seat_price_krw,
    monthCost: 0,
    renewal: dateLabel(row.contract.term_end),
    seats,
  }
}

function mapAnomaly(a, detail) {
  const project = detail?.project
  return {
    ...a,
    scopeName: a.scope_name ?? a.scope_id,
    product: a.scope_type,
    model: project?.model_id ?? '-',
    env: project?.environment ?? '-',
    dept: project?.dept_id ?? '-',
    detectedAt: dateLabel(a.created_at),
    projected: money(a.projected_monthly_cost),
    budget: project?.monthly_budget_krw ?? 0,
    monthToDate: a.observed,
    daily: detail?.series?.map((p) => money(p.cost)) ?? [a.baseline, a.observed],
    dailyStart: dateLabel(detail?.series?.[0]?.period_start),
    investigation: {
      doneAt: dateLabel(a.created_at),
      causes: [{ title: a.rule, body: '백엔드 사용량 규칙으로 감지된 비용 급증입니다.' }],
      evidence: ['사용량 시계열', '프로젝트 등록 정보'],
      actions: [{ id: 'budget_review', label: '예산 검토' }],
    },
  }
}

export async function getMe() {
  const employee = await ensureToken()
  return { name: employee.name, role: employee.role === 'admin' ? '관리자 · IT·자산관리' : employee.role }
}

export async function getProducts() {
  return (await request('/inventory')).map(mapInventory)
}

export async function getSeatRequests() {
  const page = await request('/plans?type=seat_assign')
  return page.items.map((p) => ({
    id: p.id, who: p.requested_by, product: '이용권', purpose: p.rationale,
    status: p.status === 'pending_approval' ? 'pending' : 'done',
    note: p.rationale,
  }))
}

export async function getPlans() {
  const page = await request('/plans')
  return page.items.map(mapPlan)
}

export async function getAnomalies() {
  const rows = await request('/anomalies')
  return Promise.all(rows.map(async (a) => mapAnomaly(a, await request(`/anomalies/${a.id}`))))
}

export async function getProjects() {
  const anomalies = await getAnomalies()
  return anomalies.map((a) => ({
    id: a.scope_id, name: a.scopeName, dept: a.dept, model: a.model, env: a.env,
    cost: a.monthToDate, budget: a.budget, anomaly: a.status !== 'resolved',
  }))
}

export async function getSummary() {
  const [products, plans, savings, anomalies] = await Promise.all([
    getProducts(), getPlans(), request('/savings'), request('/anomalies'),
  ])
  const seats = products.reduce((sum, p) => ({ assigned: sum.assigned + p.seatsAssigned, total: sum.total + p.seatsPurchased }), { assigned: 0, total: 0 })
  const monthCost = products.reduce((sum, p) => sum + p.monthCost, 0)
  return {
    monthCost, monthBudget: 0, seatsAssigned: seats.assigned, seatsTotal: seats.total,
    seatsToCheck: products.reduce((sum, p) => sum + p.seats.filter((s) => s.action === 'ask').length, 0),
    savingsMonth: savings.total_krw, savingsNote: '백엔드 절감 원장',
    monthly: [{ label: '현재', value: monthCost }],
    pendingAnomalies: anomalies.length,
  }
}

export async function getUpdates() {
  const page = await request('/updates')
  return page.items.map((u) => ({
    id: u.id, product: u.vendor, title: u.title, date: dateLabel(u.published_at),
    sourceUrl: u.url, note: u.summary, teams: [],
  }))
}

export async function getSuggestionStats() {
  const page = await request('/suggestions')
  const sent = page.items.filter((s) => s.status === 'sent').length
  return { collected: page.total, sent, held: page.total - sent, helpfulRate: 0, nextRun: '-' }
}

export async function getTeamSwitches() {
  return (await request('/adoption/teams')).map((t) => ({ id: t.team_id, team: t.team_name, channel: '팀', enabled: true }))
}

export async function getUnmetNeeds() {
  const rows = await request('/unmet-needs')
  return rows.map((n) => ({ capability: n.capability_tag, count: n.count, depts: Array(n.dept_count).fill('부서'), example: n.sample_summaries[0] ?? '-' }))
}

export async function getTeamAdoption() {
  const rows = await request('/adoption/teams')
  return rows.map((t) => ({ team: t.team_name, rate: Math.round(t.active_ratio * 100), seats: t.headcount }))
}

export async function getCounts() {
  const [plans, anomalies] = await Promise.all([getPlans(), request('/anomalies?status=open')])
  return {
    inbox: plans.filter((p) => p.status === 'pending_approval').length,
    cost: anomalies.length,
  }
}

export async function requestConfirmation(employeeId) {
  const plan = await request('/plans?type=seat_reclaim')
  const pending = plan.items.find((p) => p.status === 'pending_approval')
  if (!pending) throw new Error('사용 의사 확인을 만들 회수 요청이 없습니다')
  return request('/confirmations', {
    method: 'POST',
    body: JSON.stringify({ employee_id: employeeId, plan_id: pending.id, question: '현재 이용권을 계속 사용하시겠습니까?' }),
  })
}

export async function createPlanFromAnomaly(anomalyId) {
  const detail = await request(`/anomalies/${anomalyId}`)
  if (!detail.project) throw new Error('프로젝트 정보가 없어 예산 검토를 만들 수 없습니다')
  const plan = await request('/plans', {
    method: 'POST',
    body: JSON.stringify({
      type: 'budget_review',
      items: [{
        project_id: detail.project.id,
        current_budget_krw: detail.project.monthly_budget_krw,
        note: `비용 급증 알림 ${anomalyId}`,
      }],
      rationale: '비용 급증 알림에 대한 예산 검토 요청',
      evidence: [{ source: 'anomaly', ref: anomalyId, value: 'cost spike' }],
    }),
  })
  return plan.id
}

export async function approvePlan(id) {
  const plan = await request(`/plans/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ reason: '관리자 검토 후 승인' }),
  })
  if (plan.status === 'approved' && plan.risk_level !== 'high') {
    await request(`/plans/${id}/execute`, { method: 'POST', headers: { 'Idempotency-Key': `admin-web-${id}` } })
  }
  return plan.status
}

export async function rejectPlan(id) {
  const plan = await request(`/plans/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason: '관리자 검토 후 반려' }),
  })
  return plan.status
}

export async function setTeamSwitch() {
  throw new Error('팀별 자동 발송 설정 API가 아직 백엔드에 없습니다')
}
