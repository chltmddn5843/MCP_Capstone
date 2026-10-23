<script setup>
// 비용·사용량 › 벤더별: 공급사(벤더)별 이번 달 비용. 좌석 정액료(구매 좌석 × 단가, GET /inventory)와 API 사용량 비용(GET /usage scope=contract, group_by=model)을
// 공급사로 합친다. 모델별 비용·예산 도넛(홈과 같은 것)과 프로젝트별 비용 표도 여기서 본다. 팀 기준은 '팀별' 화면.
import { ref, computed, onMounted } from 'vue'
import { getProducts, getModelCostMonths, getProjects, getSummary, getModels } from '../api.js'
import { won, pct } from '../labels.js'
import ModelCostDonut from '../components/ModelCostDonut.vue'
import ProductLogo from '../components/ProductLogo.vue'

const products = ref([]), months = ref([]), projects = ref([]), s = ref(null), models = ref([])
const loaded = ref(false)
async function load() {
  ;[products.value, months.value, projects.value, s.value, models.value] = await Promise.all([
    getProducts(), getModelCostMonths().catch(() => []), getProjects().catch(() => []), getSummary(), getModels().catch(() => []),
  ])
  loaded.value = true
}
onMounted(load)

const VENDOR_KO = { openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', microsoft: 'Microsoft', adobe: 'Adobe', canva: 'Canva', xai: 'xAI', meta: 'Meta' }
const vendorName = (v) => VENDOR_KO[String(v).toLowerCase()] ?? v
// 이번 달(진행 중) 모델별 API 비용 → 모델 이름으로 공급사를 찾는다 (GET /models)
const thisMonth = computed(() => months.value.at(-1))
const apiByVendor = computed(() => {
  const out = {}
  for (const m of thisMonth.value?.models ?? []) {
    const v = models.value.find((x) => x.name === m.name)?.vendor ?? m.name.split(':')[0]
    out[v] = (out[v] ?? 0) + m.cost
  }
  return out
})
const vendors = computed(() => {
  const by = new Map()
  for (const p of products.value) {
    const v = p.vendor ?? '기타'
    const row = by.get(v) ?? { id: v, name: vendorName(v), products: [], seatCost: 0, apiCost: apiByVendor.value[v] ?? 0, seatsPurchased: 0, seatsAssigned: 0 }
    row.products.push(p); row.seatCost += p.monthCost || 0; row.seatsPurchased += p.seatsPurchased; row.seatsAssigned += p.seatsAssigned
    by.set(v, row)
  }
  for (const [v, cost] of Object.entries(apiByVendor.value)) if (!by.has(v)) by.set(v, { id: v, name: vendorName(v), products: [], seatCost: 0, apiCost: cost, seatsPurchased: 0, seatsAssigned: 0 })
  const rows = [...by.values()].map((r) => ({ ...r, total: r.seatCost + r.apiCost }))
  const sum = rows.reduce((a, r) => a + r.total, 0)
  return rows.map((r) => ({ ...r, share: pct(r.total, sum) })).sort((a, b) => b.total - a.total)
})
const total = computed(() => vendors.value.reduce((a, r) => a + r.total, 0))
const budget = computed(() => (s.value?.seatBudget ?? 0) + (s.value?.apiBudget ?? 0))
const overBudgetProjects = computed(() => projects.value.filter((p) => p.budget && p.cost > p.budget).length)
const sortedProjects = computed(() => projects.value.slice().sort((a, b) => pct(b.cost, b.budget) - pct(a.cost, a.budget) || b.cost - a.cost))
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">비용·사용량 · 벤더별</span><h1>벤더별 비용</h1></div>
    <RouterLink to="/cost/teams" class="btn">팀별 보기</RouterLink>
  </header>

  <template v-if="loaded">
    <section class="kpis" aria-label="이번 달 비용 요약">
      <div class="card-dark kpi">
        <span class="small muted">이번 달 비용 (오늘까지)</span>
        <span class="value">{{ won(total) }}</span>
        <span v-if="budget" class="xs lime">월 예산 {{ won(budget) }}의 {{ pct(total, budget) }}%</span>
        <span class="xs muted">좌석 정액 {{ won(s.seatCost) }} · API 사용량 {{ won(total - s.seatCost) }}</span>
      </div>
      <div class="card kpi">
        <span class="small muted">공급사</span>
        <span class="value">{{ vendors.length }}곳</span>
        <span class="xs muted">비용이 가장 큰 곳 {{ vendors[0]?.name ?? '-' }} ({{ vendors[0]?.share ?? 0 }}%)</span>
      </div>
      <RouterLink to="/licenses" class="card kpi">
        <span class="small muted">좌석 정액 이용권</span>
        <span class="value">{{ s.seatsAssigned }} / {{ s.seatsTotal }}석</span>
        <span class="xs muted">미배정 좌석도 돈을 냅니다 · 확인 필요 {{ s.seatsToCheck }}석</span>
      </RouterLink>
      <div class="card kpi" :class="{ 'card-lime': overBudgetProjects }">
        <span class="small" :class="{ muted: !overBudgetProjects }">예산을 넘은 API 프로젝트</span>
        <span class="value">{{ overBudgetProjects }}개</span>
        <span class="xs" :class="{ muted: !overBudgetProjects }">프로젝트 {{ projects.length }}개 중 · 아래 표에서 확인</span>
      </div>
    </section>

    <section class="card" aria-labelledby="vendor-h">
      <div class="card-head">
        <div><h2 id="vendor-h">공급사별 이번 달 비용</h2><span class="small muted">좌석 정액료 + API 사용량 비용 · 비용이 큰 공급사부터</span></div>
      </div>
      <div class="table-wrap">
        <table v-if="vendors.length" class="table" style="min-width: 760px">
          <thead><tr><th scope="col">공급사</th><th scope="col">제품 · 플랜</th><th scope="col">이용권</th><th scope="col" class="num">좌석 정액</th><th scope="col" class="num">API 사용량</th><th scope="col" class="num">합계</th><th scope="col">비중</th></tr></thead>
          <tbody>
            <tr v-for="v in vendors" :key="v.id">
              <th scope="row" class="vendor">{{ v.name }}</th>
              <td>
                <div v-for="p in v.products" :key="p.id" class="prod"><ProductLogo :tool-id="p.id" :name="p.name" :size="22" /><span>{{ p.name }} <span class="xs muted">{{ p.plan }} · {{ p.billing }}</span></span></div>
                <span v-if="!v.products.length" class="xs muted">API 사용량만</span>
              </td>
              <td>
                <div v-if="v.seatsPurchased" class="bar-inline"><div class="bar"><div :style="{ width: `${pct(v.seatsAssigned, v.seatsPurchased)}%` }" /></div><span class="small">{{ v.seatsAssigned }} / {{ v.seatsPurchased }}</span></div>
                <span v-else class="muted">-</span>
              </td>
              <td class="num">{{ v.seatCost ? won(v.seatCost) : '-' }}</td>
              <td class="num">{{ v.apiCost ? won(v.apiCost) : '-' }}</td>
              <td class="num strong">{{ won(v.total) }}</td>
              <td><div class="bar-inline"><div class="bar"><div :style="{ width: `${v.share}%` }" /></div><span class="small">{{ v.share }}%</span></div></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="small muted" style="margin: 0">아직 등록한 구독 제품이 없습니다. <RouterLink to="/setup?step=assets">회사 설정에서 제품 등록하기</RouterLink></p>
      </div>
      <p class="xs muted" style="margin: 0">좌석 정액 = 구매 좌석 × 단가(월). API 사용량 = 이번 달 오늘까지 사용 기록. 환율·세금은 계약 단가 기준입니다.</p>
    </section>

    <ModelCostDonut v-if="months.length" :months="months" />

    <section class="card" aria-labelledby="proj-h">
      <div class="card-head">
        <div><h2 id="proj-h">프로젝트별 이번 달 API 비용</h2><span class="small muted">예산 대비 비율이 높은 프로젝트부터</span></div>
      </div>
      <div class="table-wrap">
        <table v-if="sortedProjects.length" class="table" style="min-width: 720px">
          <thead><tr><th scope="col">프로젝트</th><th scope="col">담당 팀</th><th scope="col">모델</th><th scope="col">환경</th><th scope="col" class="num">이번 달</th><th scope="col">월 예산 대비</th></tr></thead>
          <tbody>
            <tr v-for="p in sortedProjects" :key="p.id">
              <th scope="row" class="vendor">{{ p.name }}</th>
              <td>{{ p.dept }}</td><td>{{ p.model }}</td><td>{{ p.env }}</td>
              <td class="num">{{ won(p.cost) }}</td>
              <td>
                <div v-if="p.budget" class="bar-inline"><div class="bar"><div :class="{ hot: p.cost > p.budget }" :style="{ width: `${Math.min(100, pct(p.cost, p.budget))}%` }" /></div><span class="small nowrap">{{ pct(p.cost, p.budget) }}% / {{ won(p.budget) }}<span v-if="p.cost > p.budget" class="pill pill-alert" style="margin-left: 8px">초과</span></span></div>
                <span v-else class="muted">예산 없음</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="small muted" style="margin: 0">아직 API 프로젝트가 없습니다.</p>
      </div>
    </section>
  </template>
  <p v-else class="card small muted loading" aria-busy="true">벤더별 비용을 불러오는 중…</p>
</template>

<style scoped>
.lime { color: var(--lime); }
.strong { font-weight: 700; }
.vendor { font-size: 14px; color: var(--ink); padding: 14px 12px 14px 0; border-top: 1px solid var(--line); vertical-align: top; }
.prod { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
.bar .hot { background: var(--lime); outline: 1px solid var(--ink); }
</style>
