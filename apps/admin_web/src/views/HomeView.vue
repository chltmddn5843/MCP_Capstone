<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getSummary, getSeatPaces, getPlans, getProducts, getMe, getModelCostMonths } from '../api.js'
import { RISK, won, pct } from '../labels.js'
import ModelCostDonut from '../components/ModelCostDonut.vue'
import ProductLogo from '../components/ProductLogo.vue'

const s = ref(null)
const heavy = ref([]) // 오늘 소비 속도 2배 이상 좌석
const plans = ref([])
const products = ref([])
const months = ref([])
const me = ref({ name: '' })
getMe().then((v) => (me.value = v)).catch(() => {})

async function load() {
  ;[s.value, heavy.value, plans.value, products.value, months.value] = await Promise.all([getSummary(), getSeatPaces().then((m) => Object.values(m).filter((p) => p.level === 'over')).catch(() => []), getPlans(), getProducts(), getModelCostMonths().catch(() => [])])
}
onMounted(() => {
  load()
  const onFocus = () => { if (document.visibilityState === 'visible') load() }  // 승인·실행 뒤 돌아오면 다시 읽는다
  window.addEventListener('focus', onFocus); document.addEventListener('visibilitychange', onFocus)
  onBeforeUnmount(() => { window.removeEventListener('focus', onFocus); document.removeEventListener('visibilitychange', onFocus) })
})

const pending = computed(() => plans.value.filter((p) => p.status === 'pending_approval'))
// 이번 달 API 사용량 비용 = 도넛의 마지막(진행 중) 달 합계
// ponytail: API 제품이 하나(Claude API)라 제품 표의 API 비용에 이 합계를 그대로 쓴다. API 계약이 늘면 제품별로 나눠 받아야 한다.
const apiCost = computed(() => months.value.at(-1)?.models.reduce((t, m) => t + m.cost, 0) ?? 0)
const today = new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
</script>

<template>
  <header class="page-head">
    <div>
      <span class="small muted">{{ today }}</span>
      <h1>안녕하세요, {{ me.name }} 님</h1>
    </div>
  </header>

  <template v-if="s">
    <section class="kpis" aria-label="핵심 지표">
      <div class="card-dark kpi">
        <span class="small muted">이번 달 비용 (오늘까지)</span>
        <span class="value">{{ won(s.seatCost + apiCost) }}</span>
        <span v-if="s.seatBudget + s.apiBudget" class="xs lime">월 예산 {{ won(s.seatBudget + s.apiBudget) }}의 {{ pct(s.seatCost + apiCost, s.seatBudget + s.apiBudget) }}%</span>
        <span class="xs muted">좌석 정액 {{ won(s.seatCost) }}<template v-if="s.seatBudget"> / {{ won(s.seatBudget) }}</template> · API 사용량 {{ won(apiCost) }}<template v-if="s.apiBudget"> / {{ won(s.apiBudget) }}</template></span>
        <RouterLink v-if="!(s.seatBudget + s.apiBudget)" to="/setup?step=budget" class="xs lime">연간 예산 설정하기</RouterLink>
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
        <RouterLink v-for="p in heavy" :key="p.employee_id" :to="{ path: '/cost/teams', query: { id: p.employee_id } }" class="feed-item">
          <span class="pill pill-alert">토큰 과사용</span>
          <div class="feed-body">
            <span class="feed-title">{{ p.employee_name }} · {{ p.product }} · 오늘 소비 속도가 평균의 {{ p.ratio }}배</span>
            <span class="small muted">오늘 예상 {{ p.projected_today.toLocaleString('ko-KR') }} 토큰 · 본인에게 Slack으로 모델 변경을 안내했습니다</span>
          </div>
        </RouterLink>
        <RouterLink v-for="p in pending" :key="p.id" :to="{ path: '/inbox', query: { id: p.id } }" class="feed-item">
          <span class="pill" :class="`pill-${RISK[p.risk].tone}`">{{ RISK[p.risk].label }}</span>
          <div class="feed-body">
            <span class="feed-title">{{ p.title }} · {{ p.subtitle }}</span>
            <span class="small muted">AI 의견: {{ p.aiOpinion.title }}</span>
          </div>
          <span class="small muted nowrap">{{ p.createdAt }}</span>
        </RouterLink>
        <RouterLink v-if="s.seatsToCheck" to="/licenses" class="feed-item">
          <span class="pill pill-neutral">이용권 확인</span>
          <div class="feed-body">
            <span class="feed-title">사용 의사를 아직 묻지 않은 이용권 {{ s.seatsToCheck }}석</span>
            <span class="small muted">장기 미사용·휴직 등 · 묻기 전에는 회수하지 않습니다</span>
          </div>
        </RouterLink>
        <p v-if="!pending.length && !s.seatsToCheck && !heavy.length" class="small muted">지금 확인할 일이 없습니다.</p>
      </section>

      <ModelCostDonut v-if="months.length" class="col-2" :months="months" />
    </div>

    <section class="card" aria-labelledby="prod-h">
      <div class="card-head">
        <h2 id="prod-h">구독 중인 제품</h2>
        <RouterLink to="/licenses" class="small strong link">전체 보기</RouterLink>
      </div>
      <div class="table-wrap">
        <table v-if="products.length" class="table" style="min-width: 720px">
          <thead><tr><th scope="col">제품</th><th scope="col">과금 방식</th><th scope="col">이용권</th><th scope="col" class="num">이번 달 비용</th><th scope="col">갱신일</th></tr></thead>
          <tbody>
            <tr v-for="p in products" :key="p.id">
              <td><div class="prod"><ProductLogo :tool-id="p.id" :name="p.name" /><div class="cell-2"><span>{{ p.name }}</span><span>{{ p.plan }} · {{ p.kind }}</span></div></div></td>
              <td>{{ p.billing }}</td>
              <td>
                <div v-if="p.seatsPurchased" class="bar-inline">
                  <div class="bar"><div :style="{ width: `${pct(p.seatsAssigned, p.seatsPurchased)}%` }" /></div>
                  <span>{{ p.seatsAssigned }} / {{ p.seatsPurchased }}</span>
                </div>
                <span v-else class="muted">좌석 없음 · 프로젝트 {{ p.projects }}개</span>
              </td>
              <td class="num">{{ won(p.monthCost ?? apiCost) }}<span v-if="p.monthCost == null" class="xs muted"><br />오늘까지 사용량</span></td>
              <td>{{ p.renewal }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="small muted" style="margin: 0">아직 등록한 구독 제품이 없습니다. <RouterLink to="/setup?step=assets">회사 설정에서 제품 등록하기</RouterLink></p>
      </div>
    </section>
  </template>
  <p v-else class="card small muted loading" aria-busy="true">이번 달 현황을 불러오는 중…</p>
</template>

<style scoped>
.lime { color: var(--lime); }
.strong { font-weight: 700; }
.prod { display: flex; align-items: center; gap: 12px; }
</style>
