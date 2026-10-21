<script setup>
import { ref, computed, onMounted } from 'vue'
import { getSummary, getAnomalies, getPlans, getProducts, getMe } from '../api.js'
import { RISK, won, pct } from '../labels.js'

const s = ref(null)
const anomalies = ref([])
const plans = ref([])
const products = ref([])
const me = ref({ name: '' })
getMe().then((v) => (me.value = v)).catch(() => {})

onMounted(async () => {
  ;[s.value, anomalies.value, plans.value, products.value] = await Promise.all([getSummary(), getAnomalies(), getPlans(), getProducts()])
})

const pending = computed(() => plans.value.filter((p) => p.status === 'pending_approval'))
const awaiting = computed(() => products.value.flatMap((p) => p.seats).filter((x) => x.action === 'remind').length)
const maxMonthly = computed(() => Math.max(...(s.value?.monthly ?? []).map((m) => m.value)))
const today = new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
</script>

<template>
  <header class="page-head">
    <div>
      <span class="small muted">{{ today }}</span>
      <h1>안녕하세요, {{ me.name }} 님</h1>
    </div>
    <label class="search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
      <span class="sr-only">검색</span>
      <input type="search" placeholder="제품·직원·처리 요청 검색">
    </label>
  </header>

  <template v-if="s">
    <section class="kpis" aria-label="핵심 지표">
      <div class="card-dark kpi">
        <span class="small muted">이번 달 구독 비용</span>
        <span class="value">{{ won(s.monthCost) }}</span>
        <span class="xs lime">월 예산 {{ won(s.monthBudget) }}의 {{ pct(s.monthCost, s.monthBudget) }}%</span>
      </div>
      <RouterLink to="/licenses" class="card kpi">
        <span class="small muted">이용권 배정</span>
        <span class="value">{{ s.seatsAssigned }} / {{ s.seatsTotal }}석</span>
        <span class="xs muted">본인 확인 필요 {{ s.seatsToCheck }}석</span>
      </RouterLink>
      <RouterLink to="/inbox" class="card-lime kpi">
        <span class="small">승인 대기</span>
        <span class="value">{{ pending.length }}건</span>
        <span class="xs">관리자 결정이 필요한 처리 요청</span>
      </RouterLink>
      <div class="card kpi">
        <span class="small muted">이번 달 절감</span>
        <span class="value">{{ won(s.savingsMonth) }}</span>
        <span class="xs muted">{{ s.savingsNote }}</span>
      </div>
    </section>

    <div class="row">
      <section class="card col-3" aria-labelledby="todo-h" style="gap: 4px">
        <div class="card-head" style="padding-bottom: 12px">
          <h2 id="todo-h">지금 확인할 일</h2>
        </div>
        <RouterLink v-for="a in anomalies.filter((x) => x.status === 'open')" :key="a.id" to="/cost" class="feed-item">
          <span class="pill pill-alert">비용 급증 알림</span>
          <div class="feed-body">
            <span class="feed-title">{{ a.scopeName }} 프로젝트 · 하루 비용이 기준의 {{ a.ratio }}배</span>
            <span class="small muted">{{ won(a.observed) }} / 기준 {{ won(a.baseline) }} · AI 조사 완료, 원인 후보 {{ a.investigation.causes.length }}개</span>
          </div>
          <span class="small muted nowrap">{{ a.detectedAt }}</span>
        </RouterLink>
        <RouterLink v-for="p in pending" :key="p.id" :to="{ path: '/inbox', query: { id: p.id } }" class="feed-item">
          <span class="pill" :class="`pill-${RISK[p.risk].tone}`">{{ RISK[p.risk].label }}</span>
          <div class="feed-body">
            <span class="feed-title">{{ p.title }} · {{ p.subtitle }}</span>
            <span class="small muted">AI 의견: {{ p.aiOpinion.title }}</span>
          </div>
          <span class="small muted nowrap">{{ p.createdAt }}</span>
        </RouterLink>
        <RouterLink v-if="awaiting" to="/licenses" class="feed-item">
          <span class="pill pill-neutral">확인 응답 대기</span>
          <div class="feed-body">
            <span class="feed-title">사용 의사 확인 {{ awaiting }}건 응답 없음</span>
            <span class="small muted">무응답이어도 이용권은 유지됩니다</span>
          </div>
        </RouterLink>
        <p v-if="!pending.length && !awaiting" class="small muted">지금 확인할 일이 없습니다.</p>
      </section>

      <section class="card col-2" aria-labelledby="trend-h">
        <div class="card-head">
          <div><h2 id="trend-h">월별 구독 비용</h2><span class="small muted">최근 6개월 · 단위 만원</span></div>
        </div>
        <div class="chart" role="img" :aria-label="s.monthly.map((m) => `${m.label} ${Math.round(m.value / 10000)}만원`).join(', ')">
          <div v-for="(m, i) in s.monthly" :key="m.label" class="chart-col">
            <span class="xs" :class="i === s.monthly.length - 1 ? 'strong' : 'muted'">{{ Math.round(m.value / 10000) }}</span>
            <div class="chart-bar" :class="{ now: i === s.monthly.length - 1 }" :style="{ height: `${(m.value / maxMonthly) * 168}px` }" />
            <span class="xs" :class="i === s.monthly.length - 1 ? 'strong' : 'muted'">{{ m.label }}</span>
          </div>
        </div>
      </section>
    </div>

    <section class="card" aria-labelledby="prod-h">
      <div class="card-head">
        <h2 id="prod-h">구독 중인 제품</h2>
        <RouterLink to="/licenses" class="small strong">전체 보기</RouterLink>
      </div>
      <div class="table-wrap">
        <table class="table" style="min-width: 720px">
          <thead><tr><th scope="col">제품</th><th scope="col">과금 방식</th><th scope="col">이용권</th><th scope="col" class="num">이번 달 비용</th><th scope="col">갱신일</th></tr></thead>
          <tbody>
            <tr v-for="p in products" :key="p.id">
              <td><div class="cell-2"><span>{{ p.name }}</span><span>{{ p.plan }} · {{ p.kind }}</span></div></td>
              <td>{{ p.billing }}</td>
              <td>
                <div v-if="p.seatsPurchased" class="bar-inline">
                  <div class="bar"><div :style="{ width: `${pct(p.seatsAssigned, p.seatsPurchased)}%` }" /></div>
                  <span>{{ p.seatsAssigned }} / {{ p.seatsPurchased }}</span>
                </div>
                <span v-else class="muted">좌석 없음 · 프로젝트 {{ p.projects }}개</span>
              </td>
              <td class="num">{{ won(p.monthCost) }}</td>
              <td>{{ p.renewal }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </template>
</template>

<style scoped>
.search { flex: 0 1 360px; min-width: 220px; display: flex; align-items: center; gap: 8px; height: 44px; padding: 0 14px; background: var(--white); border: 1px solid rgba(17, 17, 19, 0.12); border-radius: 10px; }
.search input { flex: 1; min-width: 0; border: 0; background: transparent; font-size: 14px; outline: none; }
.search:focus-within { outline: 2px solid var(--ink); outline-offset: 2px; }
.lime { color: var(--lime); }
.strong { font-weight: 700; }
.chart { height: 220px; display: flex; align-items: flex-end; gap: 12px; }
.chart-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; }
.chart-bar { width: 100%; background: rgba(17, 17, 19, 0.12); border-radius: 6px 6px 0 0; }
.chart-bar.now { background: var(--ink); }
</style>
