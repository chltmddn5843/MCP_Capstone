<script setup>
// 비용·사용량 › 팀별: 팀별 실시간 사용량(위) + 층별 좌석 배치도(아래). 직원·부서·도구는 GET /org/members, 층·구역·책상은 GET /desks (DB).
// 자리 배치·이동과 좌석 구조 편집도 여기서 한다(층 탭·구조 편집은 배치도 바로 위 툴바). 신입 등록은 회사 설정 › 부서·직원에서 한다.
// 도구는 '쓸 수 있는 것'(배정 좌석 + 팀 프로젝트 API). 좌석은 최근 30일 사용일 수도 보인다 — 관리자는 개인별 사용량을 볼 수 있지만(설계문서 3절)
// 이용권 관리 목적으로만 쓰고 인사평가에 쓰지 않는다. 팀 프로젝트 API는 개인 기록이 아니라 숫자가 없다.
// 토큰 좌석(ChatGPT 등)은 오늘 소비 속도(GET /usage/seats)로 색을 입힌다: 오늘 예상량이 같은 제품 좌석 평균 하루 사용량의 2배 이상이면 경보. 30초마다 갱신.
// 확인이 필요한 팀·자리를 고르면 오른쪽에 '왜 → AI 분석 → 해결책 선택지'(SeatInsight, insight.js 규칙)가 뜬다.
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { getOrgMembers, getSeatPaces, getSeatPaceDetail, getDesks, putDesk, addDesks, removeDesk, removeDesks, getDepartments, getModels, getOpenAlerts, getProjects, createBudgetReviewPlan, getConfirmationMap } from '../api.js'
import { FLAG, won, pct, onTabKeys, revealOnMobile } from '../labels.js'
import { errorLabel } from '../request.js'
import { seatInsight, teamBadge, teamPattern } from '../insight.js'
import ProductLogo from '../components/ProductLogo.vue'
import TeamUsage from '../components/TeamUsage.vue'
import SeatInsight from '../components/SeatInsight.vue'

// 회의실은 화면 장식. 층·구역·책상과 층 제목(그 층 구역 이름)은 책상(DB)에서 정한다
const ROOMS = { '5F': ['경영진실', '회의실 A'], '4F': ['회의실 B', '고객 상담실'], '3F': ['회의실 C', '탕비실'] }
const CLUSTER = 6 // 책상 6개(3×2 마주 보기)가 한 섬

const members = ref([])
const desks = ref([])
const depts = ref([])
const models = ref([]) // 승인 모델·단가 (가벼운 모델 추천용)
const teams = ref([]) // TeamUsage가 받은 팀별 사용량 (구역 배지·팀 카드용)
const error = ref('')
const floorId = ref('')
const deskId = ref('') // 고른 빈 자리
const teamId = ref('') // 고른 팀 (팀 카드)
const mode = ref('') // 'layout' = 좌석 구조 편집, 'team' = 팀 카드
const notice = ref({ text: '', err: false })
const detailEl = ref(null)
const toolFilter = ref('all')
const selectedId = ref(String(useRoute().query.id ?? ''))
const paces = ref({})
const alerts = ref({}) // employee_id → 본인 Slack 경보 시각 (열린 경보)
const confirmations = ref({}) // employee_id → 사용 의사 확인 요청 상태 (보냄·답함·기한 지남)
const projects = ref([]) // 팀 카드의 API 예산 검토용 (프로젝트별 이번 달 비용·예산)
const detail = ref(null)

const loadPaces = async () => {
  ;[paces.value, alerts.value] = await Promise.all([getSeatPaces().catch(() => paces.value), getOpenAlerts().catch(() => alerts.value)])
  // ?id=로 바로 들어오면 속도 목록보다 선택이 먼저라 분포가 비어 있다 → 속도가 오면 채운다
  if (selectedId.value && paces.value[selectedId.value] && !detail.value) detail.value = await getSeatPaceDetail(selectedId.value).catch(() => null)
}
let timer
async function load() {
  try { [members.value, desks.value, confirmations.value] = await Promise.all([getOrgMembers(), getDesks(), getConfirmationMap()]) } catch (e) { error.value = e.message }
}
onMounted(async () => {
  await load()
  depts.value = await getDepartments().catch(() => [])
  getModels().then((m) => (models.value = m)).catch(() => {})
  getProjects().then((p) => (projects.value = p)).catch(() => {})
  floorId.value = deskOf.value.get(selectedId.value)?.floor ?? FLOORS.value[0]?.id ?? '' // 홈에서 ?id=로 들어오면 그 사람 층으로
  await loadPaces()
  timer = setInterval(loadPaces, 30000)
})
onUnmounted(() => clearInterval(timer))

const floorNum = (id) => parseInt(id, 10)
const FLOORS = computed(() => [...new Set(desks.value.map((d) => d.floor))].sort((a, b) => floorNum(b) - floorNum(a))
  .map((id) => ({ id, label: id.replace('F', '층'), title: [...new Set(desks.value.filter((d) => d.floor === id).map((d) => deptName(d.dept_id)))].join(' · '), rooms: ROOMS[id] ?? [] })))
const floor = computed(() => FLOORS.value.find((f) => f.id === floorId.value) ?? FLOORS.value[0] ?? { id: '', label: '', title: '', rooms: [] })
// 층을 없애거나 처음 만들면 고른 층이 목록에 없을 수 있다 → 맨 위층으로
watch(FLOORS, (fs) => { if (!fs.some((f) => f.id === floorId.value)) floorId.value = fs[0]?.id ?? '' })
const byId = computed(() => new Map(members.value.map((m) => [m.id, m])))
const deskOf = computed(() => new Map(desks.value.filter((d) => d.employee_id).map((d) => [d.employee_id, d])))
const emptyDesks = computed(() => desks.value.filter((d) => !d.employee_id))
const unplaced = computed(() => members.value.filter((m) => m.status !== 'resigned' && !deskOf.value.has(m.id)))
const deptName = (id) => depts.value.find((d) => d.id === id)?.name ?? members.value.find((m) => m.dept_id === id)?.dept_name ?? id
const tools = computed(() => {
  const m = new Map()
  for (const t of members.value.flatMap((x) => x.tools)) m.set(t.tool_id, t.product)
  return [...m].map(([id, product]) => ({ id, product }))
})
const uses = (p, toolId) => p.tools.some((t) => t.tool_id === toolId)
const STATUS = { active: '재직', on_leave: '휴직 중', resigned: '퇴사' }
const needsCheck = (p) => p.status !== 'active' || p.tools.some((t) => t.flag && t.flag !== 'recent_hire')
const checkLabel = (p) => (p.status !== 'active' ? STATUS[p.status] : FLAG[p.tools.find((t) => t.flag && t.flag !== 'recent_hire')?.flag]?.label ?? '확인 필요')
// 이용권 확인이 필요한 직원을 부서별로 (팀 표의 칩·구역 배지·팀 카드가 같이 쓴다)
const checksByDept = computed(() => {
  const out = {}
  for (const p of members.value) if (p.status !== 'resigned' && needsCheck(p)) (out[p.dept_id] ??= []).push({ id: p.id, name: p.name, label: checkLabel(p) })
  return out
})
const teamOf = (deptId) => teams.value.find((t) => t.dept_id === deptId)
const apiOver = (t) => !!t?.api_budget_month_krw && t.api_cost_month_krw > t.api_budget_month_krw

// 층의 책상을 부서 구역별로 모아 6개씩 섬으로 자른다
const zones = computed(() => {
  const here = desks.value.filter((d) => d.floor === floor.value.id)
  return [...new Set(here.map((d) => d.dept_id))].map((id) => {
    const ds = here.filter((d) => d.dept_id === id).map((d) => ({ id: d.id, p: byId.value.get(d.employee_id) ?? null }))
    const people = ds.map((d) => d.p).filter(Boolean)
    const clusters = Array.from({ length: Math.ceil(ds.length / CLUSTER) }, (_, i) => ds.slice(i * CLUSTER, (i + 1) * CLUSTER))
    const count = tools.value.map((t) => ({ ...t, n: people.filter((p) => uses(p, t.id)).length })).filter((t) => t.n)
    return { id, name: deptName(id), people, clusters, count, empty: ds.length - people.length }
  })
})
// 구역 머리 배지: 이 구역에 앉은 사람 기준 (2배 이상 > API 예산 초과 > 빠름 > 이용권 확인)
const zoneBadge = (z) => teamBadge({
  over: z.people.filter((p) => pace(p)?.level === 'over').length, caution: z.people.filter((p) => pace(p)?.level === 'caution').length,
  checks: z.people.filter(needsCheck).length, apiOver: apiOver(teamOf(z.id)),
})
const floorPeople = (f) => desks.value.filter((d) => d.floor === f.id && d.employee_id).length
const floorFlags = (f) => desks.value.filter((d) => d.floor === f.id && d.employee_id).map((d) => byId.value.get(d.employee_id)).filter((p) => p && (pace(p)?.level === 'over' || needsCheck(p))).length
const selected = computed(() => members.value.find((p) => p.id === selectedId.value))
// 고른 직원의 오늘 시간대·입력 길이·모델 분포. 토큰 좌석이 없으면 not_found → 비움
watch(selectedId, async (id) => { detail.value = null; if (id && paces.value[id]) detail.value = await getSeatPaceDetail(id).catch(() => null) }, { immediate: true })
const pace = (p) => paces.value[p.id]
const PACE = { normal: '보통', caution: '빠름', over: '평균의 2배 이상' }
const n = (v) => Math.round(v).toLocaleString('ko-KR')
const paceLine = (x) => `${x.product} 오늘 ${n(x.tokens_today)} 토큰 사용 · 이 속도면 ${n(x.projected_today)} 토큰(평균 ${n(x.peer_avg_daily)}의 ${x.ratio}배, ${PACE[x.level]})`
const top = (rows) => rows.slice().sort((a, b) => b.share - a.share).slice(0, 3).map((b) => `${b.key} ${Math.round(b.share * 100)}%`).join(' · ')
const dim = (p) => toolFilter.value !== 'all' && !uses(p, toolFilter.value)
// 최근 30일 사용일: 고른 도구(전체 보기면 기록이 있는 좌석 중 가장 많이 쓴 것). 기록을 주지 않는 제품뿐이면 null
const WORKDAYS = 22 // 30일 중 평일 수. 막대 100% 기준
const days = (p) => {
  const ds = p.tools.filter((t) => t.active_days_30 != null && (toolFilter.value === 'all' || t.tool_id === toolFilter.value)).map((t) => t.active_days_30)
  return ds.length ? Math.max(...ds) : null
}
const LEVEL = (d) => (d === 0 ? '30일 미사용' : d < 5 ? '가끔' : d < 12 ? '보통' : '자주')
const zoneAvg = (z) => { const ds = z.people.map(days).filter((d) => d != null); return ds.length ? Math.round(ds.reduce((a, b) => a + b, 0) / ds.length) : null }

const VIA = { seat: '배정 좌석', project: '팀 프로젝트 API' }
const ago = (s) => (s ? `${Math.max(0, Math.round((Date.now() - new Date(s)) / 86400000))}일 전` : '기록 없음')
// 호버 툴팁·스크린리더용 한 줄: 경보 자리는 첫 번째 이유까지
const firstReason = (p) => (pace(p) && pace(p).level !== 'normal' ? seatInsight({ pace: pace(p), detail: p.id === selectedId.value ? detail.value : null, models: models.value }).reasons[0] : null)
const deskLabel = (p) => `${p.name} · ${p.job_title}${p.status !== 'active' ? ` · ${STATUS[p.status]}` : ''} · `
  + (p.tools.length ? p.tools.map((t) => t.product + (t.flag ? `(${FLAG[t.flag]?.label})` : '')).join(', ') : '쓰는 도구 없음')
  + (days(p) != null ? ` · 최근 30일 ${days(p)}일 사용(${LEVEL(days(p))})` : '')
  + (pace(p) ? ` · ${paceLine(pace(p))}` : '')
const clearNotice = () => { notice.value = { text: '', err: false } }
function pickFloor(id) { floorId.value = id; selectedId.value = ''; deskId.value = ''; teamId.value = ''; mode.value = '' }
function pickPerson(id) { selectedId.value = id; deskId.value = ''; teamId.value = ''; mode.value = ''; clearNotice(); revealOnMobile(detailEl.value) }
function pickDesk(id) { deskId.value = id; selectedId.value = ''; teamId.value = ''; mode.value = ''; clearNotice(); revealOnMobile(detailEl.value) }

const busy = ref(false)
async function run(fn, ok) {
  busy.value = true; clearNotice()
  try { await fn(); await load(); notice.value = { text: ok, err: false } } catch (e) { notice.value = { text: `실패: ${e.message}`, err: true } }
  busy.value = false
}
const moveTo = ref('')
// 앉힌 뒤에는 그 사람을 보여 준다 (빈 자리 패널이 그대로 남지 않게)
const seat = (empId, desk) => run(async () => { await putDesk(desk, empId); deskId.value = ''; selectedId.value = empId }, `${byId.value.get(empId)?.name} 님 자리를 ${desk}(으)로 정했어요.`)
const clearDesk = (desk) => run(() => putDesk(desk, null), `${desk} 자리를 비웠어요. 빈 자리는 배치도에서 눌러 없앨 수 있어요.`)

// ── 좌석 구조 편집: 층·구역·책상 만들기와 없애기 ──
// 만들기는 POST /desks 하나로: 그 층에 그 부서 구역이 있으면 끝에 붙이고, 없으면 새 구역(새 층)이 된다.
// 없애기는 비어 있는 것만 된다(서버가 앉은 사람이 있으면 막는다). 화면에서도 먼저 막고 이유를 보여 준다.
const lf = ref({ floor: '', newFloor: '', dept_id: '', count: CLUSTER })
function openLayout(z) {
  lf.value = { floor: floor.value.id || '_new', newFloor: '', dept_id: z?.id ?? depts.value[0]?.id ?? '', count: CLUSTER }
  mode.value = 'layout'; selectedId.value = ''; deskId.value = ''; teamId.value = ''; clearNotice(); revealOnMobile(detailEl.value)
}
const lfFloor = computed(() => (lf.value.floor === '_new' ? lf.value.newFloor.trim().toUpperCase().replace(/층$/, 'F').replace(/^(\d+)$/, '$1F') : lf.value.floor))
const lfExisting = computed(() => desks.value.filter((d) => d.floor === lfFloor.value && d.dept_id === lf.value.dept_id).length)
const lfError = computed(() => !/^[0-9]{1,2}F$/.test(lfFloor.value) ? '층은 숫자로 적어 주세요 (예: 6 또는 6F)'
  : !lf.value.dept_id ? '부서를 고르세요' : !(lf.value.count >= 1 && lf.value.count <= 30) ? '책상은 한 번에 1~30개까지 만들 수 있어요' : '')
const addLayout = () => {
  const { dept_id, count } = lf.value, f = lfFloor.value, existed = lfExisting.value
  return run(async () => { await addDesks(f, dept_id, Number(count)); floorId.value = f; lf.value.floor = f },
    existed ? `${f.replace('F', '층')} ${deptName(dept_id)} 구역에 책상 ${count}개를 붙였어요.` : `${f.replace('F', '층')}에 ${deptName(dept_id)} 구역을 만들고 책상 ${count}개를 놓았어요.`)
}
const zonesOf = computed(() => zones.value.map((z) => ({ ...z, size: z.clusters.flat().length })))
function removeZone(z) {
  if (!confirm(`${floor.value.label} ${z.name} 구역의 빈 책상 ${z.size}개를 모두 없앨까요?`)) return
  run(() => removeDesks(floor.value.id, z.id), `${floor.value.label} ${z.name} 구역을 없앴어요.`)
}
function removeFloor() {
  const f = floor.value
  if (!confirm(`${f.label}의 구역 ${zones.value.length}개와 빈 책상을 모두 없앨까요?`)) return
  run(() => removeDesks(f.id), `${f.label}을 없앴어요.`)
}
const removeOne = (id) => run(async () => { await removeDesk(id); deskId.value = '' }, `${id} 책상을 없앴어요.`)

// ── 팀 카드: 팀별 사용량에서 팀을 누르면 그 구역으로 가고, 오른쪽에 확인이 필요한 자리·팀 패턴·해결책을 보여 준다 ──
const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
const teamDetails = ref({}) // employee_id → SeatPaceDetail (팀 패턴용, 경보 좌석만)
async function pickTeam(deptId) {
  teamId.value = deptId; mode.value = 'team'; selectedId.value = ''; deskId.value = ''; clearNotice()
  const d = desks.value.find((x) => x.dept_id === deptId)
  if (!d) notice.value = { text: `${deptName(deptId)}은(는) 아직 자리 구역이 없어요. '좌석 구조 편집'에서 만들 수 있어요.`, err: false }
  else { floorId.value = d.floor; await nextTick(); scrollTo(`zone-${deptId}`) }
  revealOnMobile(detailEl.value)
  const alerts = (teamOf(deptId)?.alert_seats ?? []).slice(0, 6).filter((s) => !teamDetails.value[s.employee_id])
  await Promise.all(alerts.map(async (s) => { teamDetails.value[s.employee_id] = await getSeatPaceDetail(s.employee_id).catch(() => null) }))
}
const PICK_TONE = { over: 'alert', caution: 'ok' }
const team = computed(() => {
  if (!teamId.value) return null
  const t = teamOf(teamId.value), id = teamId.value
  const alerts = (t?.alert_seats ?? []).map((s) => ({ id: s.employee_id, name: s.employee_name, label: `${PACE[s.level]} ×${s.ratio}`, tone: PICK_TONE[s.level], note: `${s.product} · 오늘 예상 ${n(s.projected_today)} 토큰` }))
  for (const c of checksByDept.value[id] ?? []) if (!alerts.some((a) => a.id === c.id)) alerts.push({ id: c.id, name: c.name, label: c.label, tone: 'neutral', note: '이용권 확인 필요' })
  const insights = (t?.alert_seats ?? []).map((s) => seatInsight({ pace: paces.value[s.employee_id], detail: teamDetails.value[s.employee_id], models: models.value }))
  const pattern = teamPattern(insights)
  const fixes = [...pattern.fixes]
  if (apiOver(t)) fixes.push({ text: `API 프로젝트 비용이 월 예산을 ${won(t.api_cost_month_krw - t.api_budget_month_krw)} 넘었어요. 예산을 넘긴 프로젝트의 예산 검토 요청 만들기 (승인 대기)`, action: { kind: 'budget' } })
  if ((checksByDept.value[id] ?? []).length) fixes.push({ text: '이용권 확인이 필요한 직원은 자리를 눌러 사용 의사 확인 요청이나 회수 요청을 보내세요', action: { kind: 'none' } })
  return { id, name: deptName(id), t, alerts, badge: t ? teamBadge({ over: t.seats_over, caution: t.seats_caution, checks: (checksByDept.value[id] ?? []).length, apiOver: apiOver(t) }) : null, common: pattern.common, fixes }
})
// 팀의 예산을 넘긴 프로젝트마다 budget_review 처리 요청. 개별로 넘긴 게 없으면(팀 합계만 초과) 예산 대비 가장 큰 프로젝트 하나
const teamNote = ref({ text: '', err: false, to: '' })
async function requestBudgetReview() {
  if (!team.value || busy.value) return
  const mine = projects.value.filter((p) => p.dept === team.value.name && p.budget)
  const over = mine.filter((p) => p.cost > p.budget)
  const targets = over.length ? over : mine.slice().sort((a, b) => pct(b.cost, b.budget) - pct(a.cost, a.budget)).slice(0, 1)
  if (!targets.length) { teamNote.value = { text: '이 팀에 월 예산이 있는 API 프로젝트가 없어요.', err: true, to: '' }; return }
  busy.value = true; teamNote.value = { text: '', err: false, to: '' }
  try {
    const ids = []
    for (const p of targets) ids.push(await createBudgetReviewPlan(p.id, p.budget, `${team.value.name} ${p.name} 이번 달 ${won(p.cost)} / 예산 ${won(p.budget)} · 예산 검토`))
    teamNote.value = { text: `${targets.map((p) => p.name).join(', ')} 예산 검토 요청을 만들었어요. 관리자 승인 뒤 반영돼요.`, err: false, to: ids.length === 1 ? `/inbox?id=${ids[0]}` : '/inbox' }
  } catch (e) { teamNote.value = { text: errorLabel(e), err: true, to: '' } }
  busy.value = false
}
watch(teamId, () => { teamNote.value = { text: '', err: false, to: '' } })
// 팀 표·팀 카드에서 자리를 누르면: 그 사람 층으로 가서 책상을 고르고 보이게 한다
async function pickSeat(empId) {
  floorId.value = deskOf.value.get(empId)?.floor ?? floorId.value
  pickPerson(empId)
  await nextTick()
  if (!matchMedia('(max-width: 900px)').matches) scrollTo(`desk-${empId}`)
}
watch(selectedId, () => { moveTo.value = '' })
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">비용·사용량 · 팀별</span><h1>팀별 사용량 · 좌석 배치도</h1></div>
  </header>

  <p v-if="error" class="status err" role="alert">좌석 정보를 불러오지 못했습니다: {{ error }}</p>

  <TeamUsage :checks="checksByDept" @pick="pickTeam" @pick-seat="pickSeat" @load="teams = $event" />

  <div class="row">
    <section class="card col-3 plan" :aria-label="`${floor.label} ${floor.title} 배치도`">
      <div class="toolbar">
        <div role="tablist" aria-label="층" class="segment" @keydown="onTabKeys">
          <button v-for="f in FLOORS" :key="f.id" type="button" role="tab" :aria-selected="f.id === floorId" :tabindex="f.id === floorId ? 0 : -1" @click="pickFloor(f.id)">
            {{ f.label }} <span class="xs">{{ floorPeople(f) }}명</span><b v-if="floorFlags(f)" class="flag-n" :title="`확인 필요 ${floorFlags(f)}명`">{{ floorFlags(f) }}<span class="sr-only">명 확인 필요</span></b>
          </button>
        </div>
        <div class="tags" style="gap: 8px; align-items: center">
          <RouterLink to="/setup?step=org" class="xs muted">신입 등록은 회사 설정 › 부서·직원</RouterLink>
          <button type="button" class="btn" :aria-pressed="mode === 'layout'" @click="openLayout()">좌석 구조 편집</button>
        </div>
      </div>
      <div class="card-head">
        <div><h2>{{ floor.id ? `${floor.label} · ${floor.title}` : '좌석 배치도' }}</h2><span class="small muted">책상을 누르면 오른쪽에 쓰는 도구와 확인이 필요한 이유가 나오고, 마우스를 올리면 오늘 토큰 소비가 보입니다. 빈 자리를 누르면 사람을 앉히거나 책상을 없앨 수 있어요</span></div>
        <div class="legend">
          <span><i class="swatch" style="background: var(--white); outline: 1px solid var(--line-strong)" />재직</span>
          <span><i class="swatch hatch" />휴직·퇴사</span>
          <span><i class="swatch" style="outline: 2px dashed var(--ink); background: var(--white)" />이용권 확인 필요</span>
          <span><i class="act-legend" />최근 30일 사용일 (평일 {{ WORKDAYS }}일 = 가득)</span>
          <span><i class="swatch pace-caution" />토큰 소비 빠름 (1.5배)</span>
          <span><i class="swatch pace-over" />토큰 소비 2배 이상 · 본인 Slack 안내</span>
        </div>
      </div>
      <div class="tags filter" role="group" aria-label="도구로 강조">
        <button type="button" class="chip" :aria-pressed="toolFilter === 'all'" @click="toolFilter = 'all'">전체 보기</button>
        <button v-for="t in tools" :key="t.id" type="button" class="chip tool-chip" :aria-pressed="toolFilter === t.id" @click="toolFilter = t.id">
          <ProductLogo :tool-id="t.id" :name="t.product" :size="18" />{{ t.product }}
        </button>
      </div>

      <div v-if="!FLOORS.length && !error" class="inset empty-plan">
        <strong>아직 좌석 구조가 없습니다</strong>
        <span class="small muted">층과 부서 구역을 만들고 책상을 놓으면 직원을 앉힐 수 있어요.</span>
        <button type="button" class="btn btn-dark" style="align-self: flex-start" @click="openLayout()">좌석 구조 만들기</button>
      </div>
      <div v-else class="floor">
        <div v-for="z in zones" :id="`zone-${z.id}`" :key="z.id" class="zone" :class="{ 'zone-picked': z.id === teamId }">
          <div class="zone-head">
            <strong>{{ z.name }}</strong><span class="xs muted">{{ z.people.length }}명<template v-if="zoneAvg(z) != null"> · 평균 {{ zoneAvg(z) }}일 사용</template></span>
            <button v-if="zoneBadge(z)" type="button" class="pill zone-badge" :class="`pill-${zoneBadge(z).tone}`" @click="pickTeam(z.id)">{{ zoneBadge(z).label }}<span class="sr-only"> · 팀 카드 열기</span></button>
            <span v-for="c in z.count" :key="c.id" class="zone-count xs"><ProductLogo :tool-id="c.id" :name="c.product" :size="14" />{{ c.n }}</span>
            <span class="xs muted">빈 자리 {{ z.empty }}</span>
            <button type="button" class="link-btn xs" :disabled="busy" @click="openLayout(z)">책상 추가·구역 편집</button>
          </div>
          <div class="islands">
            <div v-for="(cl, ci) in z.clusters" :key="ci" class="island">
              <template v-for="{ id: did, p } in cl" :key="did">
                <button v-if="p" :id="`desk-${p.id}`" type="button" class="desk" :class="[{ leave: p.status !== 'active', check: needsCheck(p), dim: dim(p) }, pace(p) && `pace-${pace(p).level}`]"
                  :aria-pressed="p.id === selectedId" :aria-label="deskLabel(p)" @click="pickPerson(p.id)">
                  <span class="desk-name">{{ p.name }}<b v-if="pace(p) && pace(p).level !== 'normal'" class="pace-x">×{{ pace(p).ratio }}</b></span>
                  <span class="desk-tools">
                    <ProductLogo v-for="t in p.tools" :key="t.tool_id" :tool-id="t.tool_id" :name="t.product" :size="16" />
                    <span v-if="!p.tools.length" class="xs muted">없음</span>
                  </span>
                  <span v-if="days(p) != null" class="act" aria-hidden="true">
                    <span class="act-bar"><i :style="{ width: `${Math.min(100, (days(p) / WORKDAYS) * 100)}%` }" /></span>
                    <span class="act-n">{{ days(p) }}일</span>
                  </span>
                  <span v-if="pace(p)" class="pace-tip" aria-hidden="true">
                    <strong>{{ pace(p).product }} · 오늘 {{ PACE[pace(p).level] }}</strong>
                    <span>지금까지 {{ n(pace(p).tokens_today) }} 토큰</span>
                    <span>이 속도면 {{ n(pace(p).projected_today) }} 토큰</span>
                    <span>평균 {{ n(pace(p).peer_avg_daily) }}의 {{ pace(p).ratio }}배 · 하루 한도 {{ Math.round(pace(p).projected_quota_pct) }}% 예상</span>
                    <span v-if="firstReason(p)">{{ firstReason(p).title }} · 눌러서 이유와 해결책 보기</span>
                  </span>
                </button>
                <button v-else type="button" class="desk empty" :aria-pressed="did === deskId" :aria-label="`빈 자리 ${did}`" @click="pickDesk(did)"><span class="xs">빈 자리</span></button>
              </template>
            </div>
          </div>
        </div>
        <div class="rooms" aria-hidden="true">
          <div v-for="r in floor.rooms" :key="r" class="room">{{ r }}</div>
          <div class="room core">엘리베이터 · 계단</div>
        </div>
      </div>
      <p class="xs muted" style="margin: 0">직원·부서·도구·사용일·책상은 DB 값입니다. 사용일은 이용권 관리에만 쓰고 인사평가에 쓰지 않습니다. Acrobat·Canva는 공급사가 사용 기록을 주지 않아 마지막 사용일만 보입니다. 토큰 소비 속도 = 오늘 예상량 ÷ 같은 제품 좌석의 최근 14일 평균 하루 사용량(근무 9–18시 기준).</p>
    </section>

    <aside ref="detailEl" class="card col-1 detail" aria-live="polite" aria-labelledby="who-h">
      <p v-if="notice.text" class="status" :class="{ err: notice.err }" :role="notice.err ? 'alert' : 'status'">{{ notice.text }}</p>
      <template v-if="mode === 'layout'">
        <h2 id="who-h">좌석 구조 편집</h2>
        <form class="new-form" @submit.prevent="addLayout">
          <h3 class="small">책상 놓기</h3>
          <span class="xs muted">그 층에 그 부서 구역이 있으면 끝에 붙이고, 없으면 새 구역을 만듭니다. 책상 6개가 한 섬이에요.</span>
          <label class="field">층
            <select v-model="lf.floor"><option v-for="f in FLOORS" :key="f.id" :value="f.id">{{ f.label }}</option><option value="_new">새 층 만들기</option></select>
          </label>
          <label v-if="lf.floor === '_new'" class="field">새 층 번호<input v-model="lf.newFloor" inputmode="numeric" placeholder="예: 6" autocomplete="off" aria-describedby="lf-help" /></label>
          <label class="field">부서 구역<select v-model="lf.dept_id"><option v-for="d in depts" :key="d.id" :value="d.id">{{ d.name }}</option></select></label>
          <label class="field">책상 수<input v-model.number="lf.count" type="number" min="1" max="30" inputmode="numeric" /></label>
          <p id="lf-help" class="xs" :class="{ muted: !lfError }" style="margin: 0">
            {{ lfError || (lfExisting ? `${lfFloor.replace('F', '층')} ${deptName(lf.dept_id)} 구역(책상 ${lfExisting}개) 끝에 ${lf.count}개를 붙입니다.` : `${lfFloor.replace('F', '층')}에 ${deptName(lf.dept_id)} 구역을 새로 만듭니다.`) }}
          </p>
          <button type="submit" class="btn btn-dark" style="align-self: flex-start" :disabled="busy || !!lfError">{{ lfExisting ? '책상 붙이기' : '구역 만들기' }}</button>
        </form>
        <section v-if="floor.id" class="pace-box" aria-labelledby="zones-h">
          <h3 id="zones-h" class="small">{{ floor.label }} 구역 없애기</h3>
          <span class="xs muted">비어 있는 구역만 없앨 수 있어요. 빈 책상 하나만 없애려면 배치도에서 빈 자리를 누르세요.</span>
          <ul class="tool-list">
            <li v-for="z in zonesOf" :key="z.id">
              <div class="cell-2"><span>{{ z.name }}</span><span>책상 {{ z.size }}개 · {{ z.people.length ? `${z.people.length}명 앉아 있음` : '비어 있음' }}</span></div>
              <button type="button" class="btn btn-sm" :disabled="busy || !!z.people.length" :aria-label="`${z.name} 구역 없애기`" @click="removeZone(z)">없애기</button>
            </li>
          </ul>
          <p v-if="zonesOf.some((z) => z.people.length)" class="xs muted" style="margin: 0">사람이 앉은 구역은 그 직원들을 다른 자리로 옮기거나 자리를 비운 뒤에 없앨 수 있어요.</p>
          <button type="button" class="btn btn-sm" style="align-self: flex-start" :disabled="busy || zonesOf.some((z) => z.people.length)" @click="removeFloor">{{ floor.label }} 전체 없애기</button>
        </section>
        <button type="button" class="btn" style="align-self: flex-start" @click="mode = ''">편집 마치기</button>
      </template>
      <template v-else-if="mode === 'team' && team">
        <div class="who">
          <div class="avatar" aria-hidden="true">{{ team.name.slice(0, 1) }}</div>
          <div><h2 id="who-h">{{ team.name }}</h2>
            <span class="small muted"><template v-if="team.t">{{ team.t.headcount }}명 · 토큰 좌석 {{ team.t.seats_tracked }}석<template v-if="team.t.seats_tracked && team.t.tokens_today"> · 오늘 팀 평균의 {{ team.t.ratio }}배</template></template><template v-else>오늘 사용 기록 없음</template></span>
          </div>
        </div>
        <span v-if="team.badge" class="pill" :class="`pill-${team.badge.tone}`" style="align-self: flex-start">{{ team.badge.label }}</span>
        <section v-if="team.alerts.length" class="pace-box" aria-labelledby="alerts-h">
          <h3 id="alerts-h" class="small">확인이 필요한 자리 {{ team.alerts.length }}</h3>
          <ul class="tool-list">
            <li v-for="a in team.alerts" :key="a.id">
              <button type="button" class="seat-row" @click="pickSeat(a.id)">
                <div class="cell-2"><span>{{ a.name }}</span><span>{{ a.note }}</span></div>
                <span class="pill" :class="`pill-${a.tone}`">{{ a.label }}</span>
              </button>
            </li>
          </ul>
          <span class="xs muted">자리를 누르면 이유와 해결책, AI 분석이 열립니다.</span>
        </section>
        <p v-else class="small muted" style="margin: 0">지금 확인이 필요한 자리가 없어요.</p>
        <section v-if="team.common.length || team.fixes.length" class="pace-box" aria-labelledby="pattern-h">
          <template v-if="team.common.length">
            <h3 id="pattern-h" class="small">팀에서 보이는 패턴</h3>
            <ul class="why"><li v-for="c in team.common" :key="c.key"><strong>{{ c.title }}</strong><span class="small">{{ c.body }}</span></li></ul>
          </template>
          <template v-if="team.fixes.length">
            <h3 class="small">이렇게 해 보세요</h3>
            <ol class="how small">
              <li v-for="f in team.fixes" :key="f.text">{{ f.text }}
                <button v-if="f.action.kind === 'budget'" type="button" class="btn btn-sm btn-dark" style="margin-top: 6px" :disabled="busy" @click="requestBudgetReview">예산 검토 요청 만들기</button>
              </li>
            </ol>
            <p v-if="teamNote.text" class="status xs" :class="{ err: teamNote.err }" :role="teamNote.err ? 'alert' : 'status'" style="margin: 0">{{ teamNote.text }} <RouterLink v-if="teamNote.to" :to="teamNote.to" style="font-weight: 700; margin-left: 6px">승인 대기 보기</RouterLink></p>
          </template>
        </section>
        <section v-if="team.t?.api_cost_month_krw || team.t?.api_budget_month_krw" class="pace-box" :class="{ 'pace-over': apiOver(team.t) }" aria-labelledby="api-h">
          <h3 id="api-h" class="small">API 프로젝트 비용</h3>
          <span class="small">이번 달 {{ won(team.t.api_cost_month_krw) }}<template v-if="team.t.api_budget_month_krw"> / 월 예산 {{ won(team.t.api_budget_month_krw) }} ({{ pct(team.t.api_cost_month_krw, team.t.api_budget_month_krw) }}%)</template> · 오늘 {{ won(team.t.api_cost_today_krw) }}</span>
          <RouterLink to="/cost/vendors" class="btn btn-sm" style="align-self: flex-start">벤더별 비용에서 보기</RouterLink>
        </section>
        <button type="button" class="btn" style="align-self: flex-start" @click="mode = ''; teamId = ''">닫기</button>
      </template>
      <template v-else-if="deskId">
        <h2 id="who-h">빈 자리 {{ deskId }}</h2>
        <span class="small muted">{{ deptName(desks.find((d) => d.id === deskId)?.dept_id) }} 구역</span>
        <span class="xs muted">신입은 <RouterLink to="/setup?step=org">회사 설정 › 부서·직원</RouterLink>에서 등록한 뒤 여기서 앉힙니다.</span>
        <template v-if="unplaced.length">
          <strong class="small">자리가 없는 직원 {{ unplaced.length }}명</strong>
          <ul class="tool-list">
            <li v-for="u in unplaced" :key="u.id"><div class="cell-2"><span>{{ u.name }}</span><span>{{ u.dept_name }} · {{ u.job_title }}</span></div>
              <button type="button" class="btn" :disabled="busy" @click="seat(u.id, deskId)">여기 앉히기</button></li>
          </ul>
        </template>
        <p v-else class="small muted" style="margin: 0">자리가 없는 직원이 없어요. 다른 직원을 옮기려면 그 사람 책상을 눌러 '자리 옮기기'를 쓰세요.</p>
        <button type="button" class="btn btn-sm" style="align-self: flex-start" :disabled="busy" @click="removeOne(deskId)">이 책상 없애기</button>
      </template>
      <template v-else-if="selected">
        <div class="who">
          <div class="avatar" aria-hidden="true">{{ selected.name.slice(0, 1) }}</div>
          <div><h2 id="who-h">{{ selected.name }}</h2><span class="small muted">{{ selected.dept_name }} · {{ selected.job_title }}</span></div>
        </div>
        <span class="pill" :class="selected.status === 'active' ? 'pill-neutral' : 'pill-alert'" style="align-self: flex-start">{{ STATUS[selected.status] }}</span>
        <SeatInsight :employee="{ id: selected.id, name: selected.name }" :pace="pace(selected)" :detail="detail" :tools="selected.tools" :status="selected.status" :models="models" :alert-at="alerts[selected.id] ?? ''" :confirmation="confirmations[selected.id] ?? null" @changed="load" />
        <section v-if="pace(selected)" class="pace-box" :class="`pace-${pace(selected).level}`" aria-labelledby="pace-h">
          <h3 id="pace-h" class="small">오늘 토큰 소비 · {{ PACE[pace(selected).level] }}</h3>
          <span class="small">{{ paceLine(pace(selected)) }}</span>
          <span class="act-bar" role="img" :aria-label="`하루 한도의 ${Math.round(pace(selected).projected_quota_pct)}% 예상`"><i :style="{ width: `${Math.min(100, pace(selected).projected_quota_pct)}%` }" /></span>
          <span class="xs muted">하루 한도 {{ n(pace(selected).daily_quota) }} 토큰 중 {{ Math.round(pace(selected).quota_used_pct) }}% 사용, {{ Math.round(pace(selected).projected_quota_pct) }}% 예상</span>
          <template v-if="detail">
            <span class="xs">모델: {{ top(detail.by_model) || '없음' }}</span>
            <span class="xs">입력 길이: {{ top(detail.by_input_length) || '없음' }}</span>
            <span class="xs">많이 쓴 시간: {{ top(detail.by_hour.map((b) => ({ ...b, key: `${b.key}시` }))) || '없음' }}</span>
          </template>
        </section>
        <strong class="small">쓸 수 있는 AI·소프트웨어 {{ selected.tools.length }}개</strong>
        <ul class="tool-list">
          <li v-for="t in selected.tools" :key="t.tool_id + t.detail">
            <ProductLogo :tool-id="t.tool_id" :name="t.product" :size="32" />
            <div class="cell-2">
              <span>{{ t.product }}</span>
              <span>{{ VIA[t.via] }} · {{ t.detail }}</span>
              <span v-if="t.via === 'seat'">마지막 사용 {{ ago(t.last_activity_at) }}<template v-if="t.active_days_30 != null"> · 최근 30일 {{ t.active_days_30 }}일 · 요청 {{ (t.requests_30 ?? 0).toLocaleString('ko-KR') }}건</template></span>
              <span v-if="t.via === 'project'">팀 프로젝트라 개인 사용량은 따로 세지 않습니다</span>
            </div>
            <span v-if="t.flag" class="pill" :class="`pill-${FLAG[t.flag].tone}`">{{ FLAG[t.flag].label }}</span>
          </li>
        </ul>
        <p v-if="!selected.tools.length" class="small muted" style="margin: 0">배정된 좌석도, 팀 프로젝트 API도 없습니다.</p>
        <section class="pace-box" aria-labelledby="desk-h">
          <h3 id="desk-h" class="small">자리 · {{ deskOf.get(selected.id)?.id ?? '없음' }}</h3>
          <label class="field">옮길 빈 자리<select v-model="moveTo"><option value="" disabled>고르세요</option><option v-for="d in emptyDesks" :key="d.id" :value="d.id">{{ d.id }} · {{ deptName(d.dept_id) }}</option></select></label>
          <div class="tags" style="gap: 8px">
            <button type="button" class="btn" :disabled="!moveTo || busy" @click="seat(selected.id, moveTo)">자리 옮기기</button>
            <button v-if="deskOf.get(selected.id)" type="button" class="btn" :disabled="busy" @click="clearDesk(deskOf.get(selected.id).id)">자리 비우기</button>
          </div>
        </section>
      </template>
      <template v-else>
        <h2 id="who-h">팀이나 자리를 고르세요</h2>
        <p class="small muted" style="margin: 0">위 팀별 사용량에서 팀 이름이나 이름 칩을 누르거나, 배치도에서 책상을 누르면 확인이 필요한 이유와 해결책이 여기에 나옵니다.</p>
        <p v-if="unplaced.length" class="small" style="margin: 0">자리가 없는 직원 {{ unplaced.length }}명 · 빈 자리를 눌러 앉히세요.</p>
        <div class="tags" style="gap: 8px">
          <button type="button" class="btn" @click="openLayout()">좌석 구조 편집</button>
        </div>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }
.segment { display: flex; flex-direction: row; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 12px; background: var(--paper); border: 1px solid var(--line); }
.segment button { min-height: 40px; padding: 0 14px; border: 0; border-radius: 8px; background: transparent; font-size: 14px; display: inline-flex; align-items: center; gap: 6px; }
.segment button[aria-selected='true'] { background: var(--ink); color: var(--white); font-weight: 600; }
.flag-n { min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px; background: var(--lime); color: var(--ink); font-size: 11px; font-weight: 700; display: inline-grid; place-items: center; }
.filter { gap: 6px; }
.card-head > .legend { flex-direction: row; }
.tool-chip { display: inline-flex; align-items: center; gap: 6px; padding-left: 8px; }
.floor { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap: 16px; padding: 16px; border-radius: 12px; background: var(--paper); border: 2px solid var(--line-strong); }
.zone { display: flex; flex-direction: column; gap: 12px; padding: 14px; border-radius: 10px; background: var(--white); border: 1px solid var(--line); }
.zone.zone-picked { border: 2px solid var(--ink); }
.zone-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.zone-badge { cursor: pointer; }
.zone-count { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px 2px 4px; border-radius: 999px; border: 1px solid var(--line-strong); }
.islands { display: flex; flex-wrap: wrap; gap: 16px; }
.island { display: grid; grid-template-columns: repeat(3, minmax(0, 76px)); gap: 4px; padding: 6px; border-radius: 8px; background: var(--track); }
.desk { position: relative; min-height: 64px; padding: 6px 4px; border-radius: 6px; border: 1px solid var(--line-strong); background: var(--white); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; scroll-margin-top: 16px; }
.desk:hover { border-color: var(--ink); }
.desk[aria-pressed='true'] { background: var(--ink); color: var(--white); border-color: var(--ink); }
.desk.check { outline: 2px dashed var(--ink); outline-offset: -4px; }
.desk.leave { background: repeating-linear-gradient(45deg, var(--white) 0 6px, var(--track) 6px 12px); }
.desk.dim { opacity: 0.3; }
.desk.pace-caution, .swatch.pace-caution { background: rgba(220, 239, 109, 0.45); }
.desk.pace-over, .swatch.pace-over { background: var(--lime); border: 2px solid var(--ink); }
.desk.pace-over[aria-pressed='true'], .desk.pace-caution[aria-pressed='true'] { background: var(--ink); }
.pace-x { margin-left: 4px; font-size: 11px; }
.pace-tip { display: none; position: absolute; z-index: 5; left: 50%; bottom: calc(100% + 6px); transform: translateX(-50%); width: max-content; max-width: 240px;
  flex-direction: column; gap: 2px; padding: 8px 10px; border-radius: 8px; background: var(--ink); color: var(--white); font-size: 12px; text-align: left; pointer-events: none; }
.desk:hover .pace-tip, .desk:focus-visible .pace-tip { display: flex; }
.pace-box { display: flex; flex-direction: column; gap: 6px; padding: 12px; border-radius: 10px; border: 1px solid var(--line-strong); }
.pace-box h3 { margin: 0; }
.pace-box.pace-over { border: 2px solid var(--ink); background: rgba(220, 239, 109, 0.35); }
.why { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.why li { display: flex; flex-direction: column; gap: 2px; }
.how { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; line-height: 1.5; }
.seat-row { flex: 1; display: flex; align-items: center; gap: 12px; padding: 0; border: 0; background: none; text-align: left; min-height: 40px; }
.seat-row:hover .cell-2 > :first-child { text-decoration: underline; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.field input, .field select { min-height: 44px; border-radius: 10px; border: 1px solid var(--line-strong); background: var(--white); padding: 0 12px; font-size: 15px; font-weight: 400; width: 100%; box-sizing: border-box; }
.new-form { display: flex; flex-direction: column; gap: 12px; }
.new-form h2 { margin: 0; }
.link-btn { margin-left: auto; min-height: 32px; padding: 0 10px; border: 1px solid var(--line-strong); border-radius: 999px; background: var(--white); }
.desk.empty[aria-pressed='true'] { border: 2px solid var(--ink); color: var(--ink); }
.desk.empty { border-style: dashed; background: transparent; color: var(--muted); }
.desk-name { font-size: 13px; font-weight: 600; }
.desk-tools { display: flex; gap: 3px; min-height: 16px; }
.act { display: flex; align-items: center; gap: 4px; width: 100%; padding: 0 2px; }
.act-bar { flex: 1; height: 4px; border-radius: 999px; background: var(--track); overflow: hidden; }
.act-bar i { display: block; height: 100%; background: currentColor; }
.act-n { font-size: 11px; font-variant-numeric: tabular-nums; }
.act-legend { width: 18px; height: 4px; border-radius: 999px; display: inline-block; background: linear-gradient(90deg, var(--ink) 60%, var(--track) 60%); }
.swatch.hatch { background: repeating-linear-gradient(45deg, var(--white) 0 3px, rgba(17, 17, 19, 0.3) 3px 5px); outline: 1px solid var(--line-strong); }
.rooms { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 12px; }
.room { flex: 1 1 120px; min-height: 52px; display: grid; place-items: center; border-radius: 8px; border: 1px dashed var(--line-strong); font-size: 12px; color: var(--muted); }
.room.core { background: var(--track); border-style: solid; }
.empty-plan { gap: 10px; padding: 24px; }
.zone { scroll-margin-top: 16px; }
.detail { position: sticky; top: 24px; gap: 12px; max-height: calc(100dvh - 48px); overflow-y: auto; }
.who { display: flex; align-items: center; gap: 12px; }
.who > div:last-child { display: flex; flex-direction: column; gap: 2px; }
.avatar { width: 44px; height: 44px; border-radius: 999px; background: var(--lime); font-weight: 700; display: grid; place-items: center; flex: none; }
.tool-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; }
.tool-list li { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-top: 1px solid var(--line); }
.tool-list .cell-2 { flex: 1; min-width: 0; }
@media (max-width: 900px) { .detail { position: static; max-height: none; } .floor { padding: 8px; } .zone { padding: 10px; } .toolbar { position: sticky; top: 0; z-index: 3; background: var(--white); padding-top: 8px; } }
</style>
