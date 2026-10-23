<script setup>
// 초기 설정 마법사 (가입 직후) 겸 설정 화면 (설정을 마친 뒤). 단계: 부서·직원 → 좌석 구조(층·구역·책상) → 구독 제품(사내 자산) → AI 모델·API 프로젝트 → 연간 예산 → 확인.
// 각 단계는 저장 즉시 서버에 반영된다(감사 기록 남음). 단계 이동은 저장과 무관해 언제든 앞뒤로 갈 수 있다.
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import {
  getSetupStatus, completeSetup, getDepartments, createDepartment, createEmployees, getEmployees, getContracts, createContract,
  getModelCatalog, approveModels, importSeats, getProjects, createProject, getBudgets, setBudgets, getDesks, addDesks, removeDesk, removeDesks,
} from '../api.js'
import { BILLING, won, onTabKeys } from '../labels.js'
import { errorLabel } from '../request.js'
import ProductLogo from '../components/ProductLogo.vue'

const route = useRoute()
const router = useRouter()
const STEPS = [
  { id: 'org', label: '부서·직원' },
  { id: 'desks', label: '좌석 구조' },
  { id: 'assets', label: '구독 제품' },
  { id: 'models', label: 'AI 모델·프로젝트' },
  { id: 'budget', label: '연간 예산' },
  { id: 'done', label: '확인' },
]
const step = computed(() => STEPS.findIndex((s) => s.id === route.query.step) >= 0 ? route.query.step : 'org')
const go = (id) => { if (id !== step.value && leaveOk()) router.replace({ query: { step: id } }) }
const idx = computed(() => STEPS.findIndex((s) => s.id === step.value))
const headEl = ref(null)
watch(step, async () => { msg.value = ''; await nextTick(); headEl.value?.focus() })

const status = ref(null)
const depts = ref([])
const people = ref([])
const contracts = ref([])
const catalog = ref([])
const projects = ref([])
const budget = ref(null)
const desks = ref([])
const msg = ref('')
const busy = ref(false)

async function load() {
  ;[status.value, depts.value, people.value, contracts.value, catalog.value, projects.value, budget.value, desks.value] = await Promise.all([
    getSetupStatus(), getDepartments(), getEmployees(), getContracts(), getModelCatalog(), getProjects().catch(() => []), getBudgets(), getDesks().catch(() => []),
  ])
  bf.value = { seat: budget.value.seat_annual_krw, api: budget.value.api_annual_krw }
  picked.value = catalog.value.filter((m) => m.approved).map((m) => m.id)
}
onMounted(load)

// 저장 공통: 성공 문구 또는 오류를 한 곳(role=status/alert)에 보인다
const ok = ref(true)
const errLines = ref([])
async function save(fn, done) {
  busy.value = true; msg.value = ''; errLines.value = []
  try { const r = await fn(); await load(); ok.value = true; msg.value = typeof done === 'function' ? done(r) : done }
  catch (e) { ok.value = false; msg.value = e.message ? `${e.message}` : errorLabel(e); errLines.value = e.details?.errors ?? [] }
  finally { busy.value = false }
}

// ── 1. 부서·직원 ──
const newDept = ref('')
const csv = ref('')
const parsed = computed(() => csv.value.split('\n').map((l) => l.trim()).filter(Boolean).map((l, i) => {
  const [name, email, dept, title] = l.split(/\t|,/).map((x) => (x ?? '').trim())
  const d = depts.value.find((x) => x.name === dept)
  const err = !name ? '이름 없음' : !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email ?? '') ? '이메일 형식 아님' : !d ? `부서 '${dept ?? ''}' 없음 · 위에서 먼저 추가` : !title ? '직함 없음' : ''
  return { line: i + 1, name, email, dept, title, deptId: d?.id, err }
}))
const csvErrors = computed(() => parsed.value.filter((r) => r.err))
const addDept = () => save(async () => { await createDepartment(newDept.value.trim()); newDept.value = '' }, '부서를 추가했습니다.')
const addPeople = () => save(async () => {
  await createEmployees(parsed.value.map((r) => ({ name: r.name, email: r.email, dept_id: r.deptId, job_title: r.title })))
  csv.value = ''
}, `직원 ${parsed.value.length}명을 추가했습니다.`)
const headcount = computed(() => Object.fromEntries(depts.value.map((d) => [d.id, people.value.filter((p) => p.dept_id === d.id).length])))

// ── 2. 구독 제품 ──
const year = new Date().getFullYear()
const blank = () => ({ vendor: '', product: '', category: 'chat_assistant', kind: 'ai', plan_name: '', billing_type: 'seat_flat', seats_purchased: 10, seat_price_krw: 0, term_start: `${year}-01-01`, term_end: `${year}-12-31` })
const cf = ref(blank())
const PRESETS = [
  { vendor: 'OpenAI', product: 'ChatGPT Enterprise', category: 'chat_assistant', plan_name: 'Enterprise', billing_type: 'seat_plus_usage' },
  { vendor: 'Anthropic', product: 'Claude API', category: 'llm_api', plan_name: 'API pay-as-you-go', billing_type: 'api_usage' },
  { vendor: 'Canva', product: 'Canva Enterprise', category: 'design_collaboration', plan_name: 'Enterprise', billing_type: 'seat_flat' },
  { vendor: 'Adobe', product: 'Acrobat Pro', category: 'pdf_editor', kind: 'software', plan_name: 'Acrobat Pro Teams', billing_type: 'seat_flat' },
]
const isApi = computed(() => cf.value.billing_type === 'api_usage')
const cfError = computed(() => !cf.value.vendor.trim() || !cf.value.product.trim() || !cf.value.plan_name.trim() ? '공급사·제품·플랜 이름을 모두 입력하세요'
  : cf.value.term_end <= cf.value.term_start ? '종료일은 시작일보다 뒤여야 합니다'
  : !isApi.value && cf.value.seats_purchased < 1 ? '좌석 과금 제품은 좌석 수가 1 이상이어야 합니다' : '')
const addContract = () => save(async () => { await createContract({ ...cf.value, seats_purchased: isApi.value ? 0 : Number(cf.value.seats_purchased), seat_price_krw: Number(cf.value.seat_price_krw) }); cf.value = blank() }, '구독 제품을 등록했습니다.')
const seatMonthly = (c) => c.billing_type === 'api_usage' ? null : c.seats_purchased * c.seat_price_krw
// 이미 쓰던 회사: 공급사 관리 화면에서 내려받은 좌석 배정 목록을 그대로 넣는다 (MVP는 CSV, 후속은 SCIM)
const seatContracts = computed(() => contracts.value.filter((c) => c.billing_type !== 'api_usage'))
const sf = ref({ contract: '', csv: '' })
const readSeatFile = async (e) => { const f = e.target.files?.[0]; if (f) sf.value.csv = await f.text() }
const doImportSeats = () => save(() => importSeats(sf.value.contract, sf.value.csv).then((r) => { sf.value.csv = ''; return r }),
  (r) => `좌석 ${r.imported}석을 넣었습니다 (배정 ${r.assigned}/${r.purchased}석${r.skipped.length ? `, 이미 있던 ${r.skipped.length}명 건너뜀` : ''}).`)

// ── 3. AI 모델·프로젝트 ──
const picked = ref([])
const apiVendors = computed(() => new Set(contracts.value.filter((c) => c.billing_type === 'api_usage').map((c) => c.vendor.toLowerCase())))
// 새로 감지된 API 모델은 단가가 0(미확인)으로 들어온다. 승인하려면 공급사 가격표의 단가를 넣어야 한다 (안 넣으면 비용 추정이 0원)
const unpriced = (m) => !m.input_usd_per_mtok && !m.output_usd_per_mtok && apiVendors.value.has(m.vendor.toLowerCase())
const prices = ref({})
const needPrice = computed(() => catalog.value.filter((m) => picked.value.includes(m.id) && unpriced(m)))
watch(needPrice, (ms) => ms.forEach((m) => { prices.value[m.id] ??= { input_usd_per_mtok: null, output_usd_per_mtok: null } }), { immediate: true })
const priceMissing = computed(() => needPrice.value.some((m) => !(prices.value[m.id]?.input_usd_per_mtok > 0 && prices.value[m.id]?.output_usd_per_mtok > 0)))
const saveModels = () => save(() => approveModels(picked.value, Object.fromEntries(needPrice.value.map((m) => [m.id, prices.value[m.id]]))),
  `모델 ${picked.value.length}개를 승인 목록으로 저장했습니다.`)
const approved = computed(() => catalog.value.filter((m) => m.approved))
const pf = ref({ name: '', dept_id: '', owner_id: '', purpose: '', model_id: '', environment: 'test', monthly_budget_krw: 0 })
const owners = computed(() => people.value.filter((p) => p.dept_id === pf.value.dept_id && p.status === 'active'))
const pfError = computed(() => !pf.value.name.trim() || !pf.value.purpose.trim() ? '프로젝트 이름과 목적을 입력하세요'
  : !pf.value.dept_id || !pf.value.owner_id ? '부서와 담당자를 고르세요' : !pf.value.model_id ? '승인한 모델 중 하나를 고르세요' : '')
const addProject = () => save(async () => { await createProject({ ...pf.value, monthly_budget_krw: Number(pf.value.monthly_budget_krw) }); pf.value = { ...pf.value, name: '', purpose: '', monthly_budget_krw: 0 } }, 'API 프로젝트를 등록했습니다.')

// ── 좌석 구조: 층·부서 구역·책상 (팀별 좌석 배치도가 이 책상에 사람을 앉힌다) ──
// 만들기는 POST /desks 하나: 그 층에 그 부서 구역이 있으면 끝에 붙이고, 없으면 새 구역(새 층)이 된다. 없애기는 비어 있는 것만 (서버가 앉은 사람이 있으면 막는다).
const CLUSTER = 6 // 책상 6개가 한 섬
const lf = ref({ floor: '', newFloor: '', dept_id: '', count: CLUSTER })
const floorNum = (id) => parseInt(id, 10)
const floors = computed(() => [...new Set(desks.value.map((d) => d.floor))].sort((a, b) => floorNum(b) - floorNum(a)).map((id) => ({
  id, label: id.replace('F', '층'),
  zones: [...new Set(desks.value.filter((d) => d.floor === id).map((d) => d.dept_id))].map((dept) => {
    const ds = desks.value.filter((d) => d.floor === id && d.dept_id === dept)
    return { id: dept, name: depts.value.find((x) => x.id === dept)?.name ?? dept, size: ds.length, seated: ds.filter((d) => d.employee_id).length, empty: ds.filter((d) => !d.employee_id) }
  }),
})))
const lfFloor = computed(() => (lf.value.floor === '_new' || !lf.value.floor ? lf.value.newFloor.trim().toUpperCase().replace(/층$/, 'F').replace(/^(\d+)$/, '$1F') : lf.value.floor))
const lfExisting = computed(() => desks.value.filter((d) => d.floor === lfFloor.value && d.dept_id === lf.value.dept_id).length)
const lfError = computed(() => !/^[0-9]{1,2}F$/.test(lfFloor.value) ? '층은 숫자로 적어 주세요 (예: 4 또는 4F)'
  : !lf.value.dept_id ? '부서를 고르세요' : !(lf.value.count >= 1 && lf.value.count <= 30) ? '책상은 한 번에 1~30개까지 만들 수 있어요' : '')
const addLayout = () => {
  const { dept_id, count } = lf.value, f = lfFloor.value, existed = lfExisting.value, name = depts.value.find((x) => x.id === dept_id)?.name ?? dept_id
  return save(async () => { await addDesks(f, dept_id, Number(count)); lf.value = { ...lf.value, floor: f, newFloor: '' } },
    existed ? `${f.replace('F', '층')} ${name} 구역에 책상 ${count}개를 붙였어요.` : `${f.replace('F', '층')}에 ${name} 구역을 만들고 책상 ${count}개를 놓았어요.`)
}
function removeZone(f, z) {
  if (!confirm(`${f.label} ${z.name} 구역의 빈 책상 ${z.size}개를 모두 없앨까요?`)) return
  save(() => removeDesks(f.id, z.id), `${f.label} ${z.name} 구역을 없앴어요.`)
}
function removeFloor(f) {
  if (!confirm(`${f.label}의 구역 ${f.zones.length}개와 빈 책상을 모두 없앨까요?`)) return
  save(() => removeDesks(f.id), `${f.label}을 없앴어요.`)
}
const removeEmptyOne = (f, z) => save(() => removeDesk(z.empty[z.empty.length - 1].id), `${f.label} ${z.name} 구역의 빈 책상 하나를 없앴어요.`)

// ── 4. 예산 ──
const bf = ref({ seat: 0, api: 0 })
const saveBudget = () => save(() => setBudgets({ fiscal_year: budget.value.fiscal_year, seat_annual_krw: Number(bf.value.seat), api_annual_krw: Number(bf.value.api) }), '연간 예산을 저장했습니다.')
const seatOver = computed(() => budget.value && budget.value.seat_monthly_cost_krw > Math.floor(bf.value.seat / 12))
const apiOver = computed(() => budget.value && budget.value.project_budget_sum_krw > Math.floor(bf.value.api / 12))

// 단계 이동은 저장과 무관하다. [저장]을 누르지 않고 옮기면 입력이 서버에 남지 않으므로 그때만 한 번 묻는다.
const dirty = computed(() => ({
  org: !!(newDept.value.trim() || csv.value.trim()),
  desks: !!lf.value.newFloor.trim(),
  assets: JSON.stringify(cf.value) !== JSON.stringify(blank()),
  models: picked.value.length !== approved.value.length || picked.value.some((id) => !approved.value.some((m) => m.id === id)) || !!(pf.value.name.trim() || pf.value.purpose.trim()),
  budget: !!budget.value && (Number(bf.value.seat) !== budget.value.seat_annual_krw || Number(bf.value.api) !== budget.value.api_annual_krw),
})[step.value] ?? false)
const leaveOk = () => !dirty.value || confirm(`'${STEPS[idx.value].label}'에 저장하지 않은 입력이 있어요. 저장하지 않고 이동할까요?`)
onBeforeRouteLeave(leaveOk)
const onUnload = (e) => { if (dirty.value) e.preventDefault() } // 새로고침·탭 닫기
window.addEventListener('beforeunload', onUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', onUnload))

// ── 5. 확인 ──
const finish = () => save(async () => { await completeSetup(); router.push('/') }, '설정을 마쳤습니다.')
const CHECK = computed(() => status.value && [
  { label: '부서', n: status.value.steps.departments, unit: '개', need: 1, step: 'org' },
  { label: '직원', n: status.value.steps.employees, unit: '명', need: 1, step: 'org' },
  { label: '구독 제품', n: status.value.steps.contracts, unit: '개', need: 1, step: 'assets', required: true },
  { label: '승인한 AI 모델', n: status.value.steps.models, unit: '개', need: 0, step: 'models' },
  { label: 'API 프로젝트', n: status.value.steps.projects, unit: '개', need: 0, step: 'models' },
  { label: `${budget.value?.fiscal_year}년 예산 (좌석·API)`, n: status.value.steps.budgets, unit: '개 항목', need: 2, step: 'budget', required: true },
])
const canFinish = computed(() => CHECK.value?.filter((c) => c.required).every((c) => c.n >= c.need))
</script>

<template>
  <header class="page-head">
    <div>
      <span class="small muted">{{ status?.company_name }} · {{ status?.setup_completed ? '설정' : '초기 설정' }}</span>
      <h1>{{ status?.setup_completed ? '회사 설정' : '처음 설정하기' }}</h1>
    </div>
  </header>

  <ol class="stepper" role="tablist" aria-label="설정 단계" @keydown="onTabKeys">
    <li v-for="(s, i) in STEPS" :key="s.id" role="presentation">
      <button type="button" role="tab" :aria-selected="s.id === step" :tabindex="s.id === step ? 0 : -1" :class="{ past: i < idx }" @click="go(s.id)">
        <span class="n" aria-hidden="true">{{ i + 1 }}</span>{{ s.label }}
      </button>
    </li>
  </ol>

  <p v-if="msg" :class="ok ? 'status' : 'status err'" :role="ok ? 'status' : 'alert'">{{ msg }}</p>
  <ul v-if="errLines.length" class="errs" role="alert"><li v-for="l in errLines" :key="l">{{ l }}</li></ul>

  <section v-if="status" class="card body" role="tabpanel">
    <h2 ref="headEl" tabindex="-1">{{ idx + 1 }}. {{ STEPS[idx].label }}</h2>

    <!-- 1. 부서·직원 -->
    <template v-if="step === 'org'">
      <p class="small muted">좌석 배치도·팀 활용 현황은 이 부서·직원 기준으로 만듭니다. 직원 계정은 비밀번호 없이 만들어지고, 로그인은 각자 설정한 뒤에 할 수 있습니다.</p>
      <div class="split">
        <div class="stack" style="gap: 10px">
          <strong class="small">부서 {{ depts.length }}개</strong>
          <ul class="list">
            <li v-for="d in depts" :key="d.id"><span>{{ d.name }}</span><span class="small muted">{{ headcount[d.id] }}명</span></li>
          </ul>
          <form class="inline" @submit.prevent="addDept">
            <label class="field grow">새 부서 이름<input v-model="newDept" placeholder="예: 마케팅" /></label>
            <button type="submit" class="btn" :disabled="busy || !newDept.trim()">부서 추가</button>
          </form>
        </div>
        <form class="stack" style="gap: 10px" @submit.prevent="addPeople">
          <label class="field" for="csv">직원 붙여넣기 <span class="xs muted">한 줄에 한 명 · 이름, 이메일, 부서, 직함 (쉼표 또는 탭, 엑셀에서 복사 가능)</span>
            <textarea id="csv" v-model="csv" rows="6" placeholder="김민서, minseo@company.co.kr, 마케팅, 콘텐츠 마케터" aria-describedby="csv-help" />
          </label>
          <span id="csv-help" class="xs muted">현재 직원 {{ people.length }}명</span>
          <ul v-if="csvErrors.length" class="errs" role="alert">
            <li v-for="r in csvErrors" :key="r.line">{{ r.line }}행 · {{ r.err }}</li>
          </ul>
          <p v-else-if="parsed.length" class="small" style="margin: 0">{{ parsed.length }}명 추가 준비됨</p>
          <button type="submit" class="btn btn-dark" :disabled="busy || !parsed.length || !!csvErrors.length">직원 {{ parsed.length || '' }}명 추가</button>
        </form>
      </div>
    </template>

    <!-- 2. 좌석 구조 -->
    <template v-else-if="step === 'desks'">
      <p class="small muted">층과 부서 구역에 책상을 놓습니다. 사람을 앉히고 옮기는 건 비용·사용량 › 팀별 좌석 배치도에서 합니다. 책상 6개가 한 섬이에요.</p>
      <div class="split">
        <form class="stack form" @submit.prevent="addLayout">
          <strong class="small">책상 놓기</strong>
          <div class="grid">
            <label class="field">층
              <select v-model="lf.floor"><option value="" disabled>고르세요</option><option v-for="f in floors" :key="f.id" :value="f.id">{{ f.label }}</option><option value="_new">새 층 만들기</option></select>
            </label>
            <label v-if="lf.floor === '_new' || !floors.length" class="field">새 층 번호<input v-model="lf.newFloor" inputmode="numeric" placeholder="예: 4" autocomplete="off" /></label>
            <label class="field">부서 구역<select v-model="lf.dept_id"><option value="" disabled>고르세요</option><option v-for="d in depts" :key="d.id" :value="d.id">{{ d.name }}</option></select></label>
            <label class="field">책상 수<input v-model.number="lf.count" type="number" min="1" max="30" inputmode="numeric" /></label>
          </div>
          <p class="xs" :class="{ muted: !lfError }" style="margin: 0">{{ lfError || (lfExisting ? `${lfFloor.replace('F', '층')} 그 구역(책상 ${lfExisting}개) 끝에 ${lf.count}개를 붙입니다.` : `${lfFloor.replace('F', '층')}에 새 구역을 만듭니다.`) }}</p>
          <button type="submit" class="btn btn-dark" style="align-self: flex-start" :disabled="busy || !!lfError">{{ lfExisting ? '책상 붙이기' : '구역 만들기' }}</button>
        </form>
        <div class="stack" style="gap: 10px">
          <strong class="small">현재 구조 · 책상 {{ desks.length }}개</strong>
          <p v-if="!floors.length" class="small muted" style="margin: 0">아직 층이 없습니다. 왼쪽에서 첫 구역을 만드세요.</p>
          <div v-for="f in floors" :key="f.id" class="bcard">
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
              <strong>{{ f.label }}</strong>
              <button type="button" class="btn btn-sm" :disabled="busy || f.zones.some((z) => z.seated)" :title="f.zones.some((z) => z.seated) ? '사람이 앉아 있는 층은 없앨 수 없어요' : ''" @click="removeFloor(f)">층 전체 없애기</button>
            </div>
            <ul class="list">
              <li v-for="z in f.zones" :key="z.id">
                <span>{{ z.name }} <span class="small muted">책상 {{ z.size }}개 · {{ z.seated ? `${z.seated}명 앉음` : '비어 있음' }}</span></span>
                <span class="inline" style="gap: 6px">
                  <button type="button" class="btn btn-sm" :disabled="busy || !z.empty.length" @click="removeEmptyOne(f, z)">빈 책상 1개 빼기</button>
                  <button type="button" class="btn btn-sm" :disabled="busy || !!z.seated" @click="removeZone(f, z)">구역 없애기</button>
                </span>
              </li>
            </ul>
          </div>
          <span class="xs muted">사람이 앉은 구역·층은 팀별 좌석 배치도에서 자리를 비운 뒤 없앨 수 있어요.</span>
        </div>
      </div>
    </template>

    <!-- 3. 구독 제품 -->
    <template v-else-if="step === 'assets'">
      <p class="small muted">회사가 계약한 AI·소프트웨어(사내 자산)입니다. 좌석형은 구매 좌석 수와 단가, API형은 사용량 과금이라 좌석이 없습니다.</p>
      <div v-if="contracts.length" class="table-wrap">
        <table class="table" style="min-width: 640px">
          <thead><tr><th scope="col">제품</th><th scope="col">과금 방식</th><th scope="col" class="num">좌석</th><th scope="col" class="num">월 좌석료</th><th scope="col">계약 기간</th></tr></thead>
          <tbody>
            <tr v-for="c in contracts" :key="c.id">
              <td><div class="prod"><ProductLogo :tool-id="c.toolId" :name="c.product" /><div class="cell-2"><span>{{ c.product }}</span><span>{{ c.vendor }} · {{ c.plan_name }}</span></div></div></td>
              <td>{{ BILLING[c.billing_type] }}</td>
              <td class="num">{{ c.billing_type === 'api_usage' ? '-' : `${c.seats_purchased}석` }}</td>
              <td class="num">{{ seatMonthly(c) == null ? '사용량 과금' : won(seatMonthly(c)) }}</td>
              <td class="nowrap">{{ c.term_start.slice(0, 10) }} ~ {{ c.term_end.slice(0, 10) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="inset small" style="margin: 0">아직 등록한 제품이 없습니다. 아래에서 첫 제품을 등록하세요.</p>

      <form v-if="seatContracts.length" class="stack form" @submit.prevent="doImportSeats">
        <strong class="small">이미 쓰던 좌석 가져오기 <span class="muted">· 공급사 관리 화면에서 내려받은 사용자 목록. 넣지 않으면 모든 좌석이 비어 있는 것으로 보여 신청 즉시 배정됩니다</span></strong>
        <div class="grid">
          <label class="field">제품
            <select id="seat-contract" v-model="sf.contract"><option value="" disabled>고르세요</option><option v-for="c in seatContracts" :key="c.id" :value="c.id">{{ c.product }} · {{ c.seats_purchased }}석</option></select>
          </label>
          <label class="field">CSV 파일<input id="seat-file" type="file" accept=".csv,text/csv" @change="readSeatFile" /></label>
        </div>
        <label class="field" for="seat-csv">또는 붙여넣기 <span class="xs muted">첫 줄 머리글 email,last_activity_at · 마지막 사용일(YYYY-MM-DD)을 비우면 '기록 없음(확인 필요)'</span>
          <textarea id="seat-csv" v-model="sf.csv" rows="4" placeholder="email,last_activity_at&#10;minseo@company.co.kr,2026-10-20&#10;jiho@company.co.kr," />
        </label>
        <button type="submit" class="btn" style="align-self: flex-start" :disabled="busy || !sf.contract || !sf.csv.trim()">좌석 가져오기</button>
      </form>

      <form class="stack form" @submit.prevent="addContract">
        <div class="tags" role="group" aria-label="자주 쓰는 제품으로 채우기">
          <span class="small muted" style="align-self: center">빠르게 채우기</span>
          <button v-for="p in PRESETS" :key="p.product" type="button" class="chip chip-lg tool-chip" @click="cf = { ...blank(), ...p }">
            <ProductLogo tool-id="" :name="p.product" :size="22" />{{ p.product }}
          </button>
        </div>
        <div class="grid">
          <label class="field">공급사<input v-model="cf.vendor" placeholder="예: OpenAI" /></label>
          <label class="field">제품<input v-model="cf.product" placeholder="예: ChatGPT Enterprise" /></label>
          <label class="field">플랜<input v-model="cf.plan_name" placeholder="예: Enterprise" /></label>
          <label class="field">과금 방식
            <select v-model="cf.billing_type"><option v-for="(l, k) in BILLING" :key="k" :value="k">{{ l }}</option></select>
          </label>
          <label v-if="!isApi" class="field">구매 좌석 수<input v-model.number="cf.seats_purchased" type="number" min="1" inputmode="numeric" /></label>
          <label v-if="!isApi" class="field">좌석 단가(월, 원)<input v-model.number="cf.seat_price_krw" type="number" min="0" step="1000" inputmode="numeric" /></label>
          <label class="field">계약 시작<input v-model="cf.term_start" type="date" /></label>
          <label class="field">계약 종료<input v-model="cf.term_end" type="date" /></label>
        </div>
        <p v-if="!isApi && cf.seats_purchased && cf.seat_price_krw" class="small" style="margin: 0">월 좌석료 {{ won(cf.seats_purchased * cf.seat_price_krw) }} · 연 {{ won(cf.seats_purchased * cf.seat_price_krw * 12) }}</p>
        <p v-if="cfError" class="xs muted" style="margin: 0">{{ cfError }}</p>
        <button type="submit" class="btn btn-dark" style="align-self: flex-start" :disabled="busy || !!cfError">제품 등록</button>
      </form>
    </template>

    <!-- 3. AI 모델·프로젝트 -->
    <template v-else-if="step === 'models'">
      <p class="small muted">직원과 API 프로젝트가 쓸 수 있는 모델을 고릅니다. 단가는 공급사 공식 가격(100만 토큰당 달러)입니다. API 계약이 있는 공급사의 모델만 실제로 호출할 수 있습니다.</p>
      <form class="stack" style="gap: 10px" @submit.prevent="saveModels">
        <fieldset class="models">
          <legend class="sr-only">승인할 모델</legend>
          <label v-for="m in catalog" :key="m.id" class="model" :class="{ on: picked.includes(m.id) }">
            <input v-model="picked" type="checkbox" :value="m.id" />
            <span class="cell-2" style="flex: 1; min-width: 0">
              <span>{{ m.name }} <span class="xs muted">{{ m.vendor }}</span></span>
              <span>{{ m.capabilities }}</span>
            </span>
            <span v-if="unpriced(m)" class="pill pill-neutral">새로 감지 · 단가 미확인</span>
            <span v-else class="price small">입력 ${{ m.input_usd_per_mtok }} · 출력 ${{ m.output_usd_per_mtok }}</span>
            <span v-if="!apiVendors.has(m.vendor.toLowerCase())" class="pill pill-neutral">API 계약 없음</span>
          </label>
        </fieldset>
        <div v-for="m in needPrice.filter((x) => prices[x.id])" :key="m.id" class="grid">
          <label class="field">{{ m.name }} 입력 단가 (100만 토큰당 $)<input :id="`in-${m.id}`" v-model.number="prices[m.id].input_usd_per_mtok" type="number" min="0" step="0.01" inputmode="decimal" /></label>
          <label class="field">{{ m.name }} 출력 단가 (100만 토큰당 $)<input :id="`out-${m.id}`" v-model.number="prices[m.id].output_usd_per_mtok" type="number" min="0" step="0.01" inputmode="decimal" /></label>
        </div>
        <p v-if="priceMissing" class="xs muted" style="margin: 0">새로 감지된 API 모델은 공급사 가격표의 단가를 넣어야 승인할 수 있습니다.</p>
        <button type="submit" class="btn btn-dark" style="align-self: flex-start" :disabled="busy || priceMissing">승인 목록 저장 ({{ picked.length }}개)</button>
      </form>

      <hr />
      <strong class="small">API 프로젝트 {{ projects.length }}개 <span class="muted">· 프로젝트별 월 예산이 비용 급증 알림과 홈 도넛의 기준이 됩니다</span></strong>
      <ul v-if="projects.length" class="list">
        <li v-for="p in projects" :key="p.id"><span>{{ p.name }} <span class="xs muted">{{ p.dept }} · {{ p.model }} · {{ p.env }}</span></span><span class="small">월 {{ won(p.budget) }}</span></li>
      </ul>
      <form class="stack form" @submit.prevent="addProject">
        <div class="grid">
          <label class="field">프로젝트 이름<input v-model="pf.name" placeholder="예: 고객 문의 분류" /></label>
          <label class="field">부서
            <select v-model="pf.dept_id" @change="pf.owner_id = ''"><option value="" disabled>고르세요</option><option v-for="d in depts" :key="d.id" :value="d.id">{{ d.name }}</option></select>
          </label>
          <label class="field">담당자
            <select v-model="pf.owner_id" :disabled="!pf.dept_id"><option value="" disabled>{{ pf.dept_id ? (owners.length ? '고르세요' : '이 부서에 직원 없음') : '부서 먼저' }}</option><option v-for="p in owners" :key="p.id" :value="p.id">{{ p.name }} · {{ p.job_title }}</option></select>
          </label>
          <label class="field">모델
            <select v-model="pf.model_id"><option value="" disabled>{{ approved.length ? '고르세요' : '먼저 위에서 승인' }}</option><option v-for="m in approved" :key="m.id" :value="m.id">{{ m.name }}</option></select>
          </label>
          <label class="field">환경
            <select v-model="pf.environment"><option value="test">테스트</option><option value="prod">운영</option></select>
          </label>
          <label class="field">월 예산(원)<input v-model.number="pf.monthly_budget_krw" type="number" min="0" step="10000" inputmode="numeric" /></label>
        </div>
        <label class="field">목적<input v-model="pf.purpose" placeholder="예: 하루 1,000건 문의를 10개 유형으로 분류" /></label>
        <p v-if="pfError" class="xs muted" style="margin: 0">{{ pfError }}</p>
        <button type="submit" class="btn btn-dark" style="align-self: flex-start" :disabled="busy || !!pfError">프로젝트 등록</button>
      </form>
    </template>

    <!-- 4. 예산 -->
    <form v-else-if="step === 'budget' && budget" class="stack form" @submit.prevent="saveBudget">
      <p class="small muted" style="margin: 0">{{ budget.fiscal_year }}년 AI·소프트웨어 연간 예산입니다. 월 예산은 12로 나눠 홈 화면의 예산 대비 비교에 씁니다.</p>
      <div class="grid two-col">
        <div class="bcard">
          <label class="field">좌석 구독 연간 예산(원)<input v-model.number="bf.seat" type="number" min="0" step="100000" inputmode="numeric" aria-describedby="seat-help" /></label>
          <span id="seat-help" class="small">월 {{ won(Math.floor(bf.seat / 12)) }} · 지금 좌석료 월 {{ won(budget.seat_monthly_cost_krw) }}</span>
          <span v-if="seatOver" class="pill pill-alert" style="align-self: flex-start">지금 좌석료가 월 예산을 넘습니다</span>
          <button type="button" class="btn btn-sm" style="align-self: flex-start" @click="bf.seat = budget.seat_monthly_cost_krw * 12">지금 좌석료 × 12로 채우기</button>
        </div>
        <div class="bcard">
          <label class="field">API 사용량 연간 예산(원)<input v-model.number="bf.api" type="number" min="0" step="100000" inputmode="numeric" aria-describedby="api-help" /></label>
          <span id="api-help" class="small">월 {{ won(Math.floor(bf.api / 12)) }} · 프로젝트 월 예산 합 {{ won(budget.project_budget_sum_krw) }}</span>
          <span v-if="apiOver" class="pill pill-alert" style="align-self: flex-start">프로젝트 예산 합이 월 예산을 넘습니다</span>
          <button type="button" class="btn btn-sm" style="align-self: flex-start" @click="bf.api = budget.project_budget_sum_krw * 12">프로젝트 예산 합 × 12로 채우기</button>
        </div>
      </div>
      <p class="small" style="margin: 0"><strong>연간 합계 {{ won(Number(bf.seat) + Number(bf.api)) }}</strong> · 월 {{ won(Math.floor((Number(bf.seat) + Number(bf.api)) / 12)) }}</p>
      <button type="submit" class="btn btn-dark" style="align-self: flex-start" :disabled="busy">예산 저장</button>
    </form>

    <!-- 5. 확인 -->
    <template v-else-if="step === 'done'">
      <ul class="list">
        <li v-for="c in CHECK" :key="c.label">
          <span>{{ c.label }} <span v-if="c.required" class="xs muted">필수</span></span>
          <span class="tags" style="align-items: center">
            <span class="pill" :class="c.n >= c.need && c.n ? 'pill-ok' : c.required ? 'pill-alert' : 'pill-neutral'">{{ c.n ? `${c.n}${c.unit}` : '없음' }}</span>
            <button type="button" class="btn btn-sm" @click="go(c.step)">고치기</button>
          </span>
        </li>
      </ul>
      <button v-if="!status.setup_completed" type="button" class="btn btn-primary" style="align-self: flex-start; min-height: 48px" :disabled="busy || !canFinish" @click="finish">
        {{ canFinish ? '설정 마치고 홈으로' : '필수 항목(구독 제품·올해 예산)을 먼저 채우세요' }}
      </button>
      <p v-else class="small muted" style="margin: 0">설정을 마친 회사입니다. 바꾼 내용은 저장할 때마다 바로 반영됩니다.</p>
    </template>

    <div class="nav">
      <button v-if="idx > 0" type="button" class="btn" @click="go(STEPS[idx - 1].id)">이전</button>
      <button v-if="idx < STEPS.length - 1" type="button" class="btn btn-dark" @click="go(STEPS[idx + 1].id)">다음: {{ STEPS[idx + 1].label }}</button>
    </div>
  </section>
</template>

<style scoped>
.stepper { margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 8px; }
.stepper button { min-height: 44px; padding: 0 14px 0 8px; border-radius: 999px; border: 1px solid var(--line-strong); background: var(--white); display: inline-flex; align-items: center; gap: 8px; font-size: 14px; }
.stepper .n { width: 28px; height: 28px; border-radius: 999px; display: grid; place-items: center; background: var(--paper); font-weight: 700; font-size: 13px; }
.stepper button.past .n { background: var(--lime); }
.stepper button[aria-selected='true'] { background: var(--ink); color: var(--white); border-color: var(--ink); font-weight: 600; }
.stepper button[aria-selected='true'] .n { background: var(--lime); color: var(--ink); }
.body { gap: 18px; }
.body h2:focus { outline: none; }
.split { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: 24px; align-items: start; }
.list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; }
.list li { display: flex; justify-content: space-between; align-items: center; gap: 12px; min-height: 44px; border-top: 1px solid var(--line); font-size: 14px; }
.inline { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px; }
.grow { flex: 1 1 200px; }
.form { gap: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.field input, .field select, .field textarea { min-height: 44px; border-radius: 10px; border: 1px solid var(--line-strong); background: var(--white); padding: 0 12px; font-size: 15px; font-weight: 400; width: 100%; }
.field textarea { padding: 10px 12px; font-family: inherit; resize: vertical; }
.errs { margin: 0; padding: 10px 12px 10px 28px; border-radius: 10px; background: var(--ink); color: var(--lime); font-size: 13px; }
.prod { display: flex; align-items: center; gap: 12px; }
.tool-chip { display: inline-flex; align-items: center; gap: 8px; padding-left: 8px; }
.models { margin: 0; padding: 0; border: 0; display: flex; flex-direction: column; gap: 8px; }
.model { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--line-strong); cursor: pointer; }
.model.on { border: 2px solid var(--ink); padding: 11px 13px; }
.model input { width: 20px; height: 20px; accent-color: var(--ink); margin: 0; }
.price { font-variant-numeric: tabular-nums; }
hr { border: 0; border-top: 1px solid var(--line); margin: 4px 0; width: 100%; }
.two-col { grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); }
.bcard { display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: 12px; background: var(--paper); }
.nav { display: flex; justify-content: space-between; gap: 8px; padding-top: 16px; border-top: 1px solid var(--line); }
.nav .btn-dark { margin-left: auto; }
</style>
