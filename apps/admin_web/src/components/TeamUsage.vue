<script setup>
// 팀별 오늘 사용량 (GET /usage/teams). 좌석 토큰은 좌석 배치도와 같은 소비 속도 기준을 팀으로 합친 것, API는 팀 프로젝트 비용. 30초마다 갱신.
// 팀 이름을 누르면 좌석 배치도가 그 팀 구역이 있는 층으로 간다(pick).
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getTeamUsage } from '../api.js'
import { won, pct } from '../labels.js'

const emit = defineEmits(['pick'])
const teams = ref(null)
const at = ref('')
const failed = ref(false)
async function load() {
  try {
    teams.value = await getTeamUsage()
    at.value = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    failed.value = false
  } catch { failed.value = true } // 이전 값은 그대로 두고 '갱신 실패'만 알린다
}
let timer
onMounted(() => { load(); timer = setInterval(load, 30000) })
onUnmounted(() => clearInterval(timer))

const n = (v) => Math.round(v).toLocaleString('ko-KR')
const sum = (k) => (teams.value ?? []).reduce((s, t) => s + t[k], 0)
const total = computed(() => teams.value && {
  tokens: sum('tokens_today'), projected: sum('projected_today'), over: sum('seats_over'), caution: sum('seats_caution'),
  apiToday: sum('api_cost_today_krw'), apiMonth: sum('api_cost_month_krw'), budget: sum('api_budget_month_krw'),
})
const RATIO_FULL = 2.5 // 막대 끝 = 평균의 2.5배
const pace = (t) => (!t.seats_tracked ? '' : t.ratio >= 2 ? '2배 이상' : t.ratio >= 1.5 ? '빠름' : '보통')
</script>

<template>
  <section class="card" aria-labelledby="tu-h">
    <div class="card-head">
      <div>
        <h2 id="tu-h">팀별 실시간 사용량</h2>
        <span class="small muted">오늘 기준 · 30초마다 갱신<template v-if="at"> · 마지막 {{ at }}</template><template v-if="failed"> · 갱신 실패, 이전 값을 보여 줍니다</template></span>
      </div>
    </div>

    <p v-if="!teams" class="small muted loading" aria-busy="true">팀별 사용량을 불러오는 중…</p>
    <p v-else-if="!teams.length" class="small muted loading">아직 사용 기록이 있는 팀이 없습니다.</p>
    <template v-else>
      <div class="sum">
        <div><span class="xs muted">좌석 토큰 오늘</span><strong>{{ n(total.tokens) }}</strong><span class="xs muted">이 속도면 {{ n(total.projected) }}</span></div>
        <div><span class="xs muted">소비 경보 좌석</span><strong>{{ total.over }}석</strong><span class="xs muted">2배 이상 · 빠름 {{ total.caution }}석</span></div>
        <div><span class="xs muted">API 비용 오늘</span><strong>{{ won(total.apiToday) }}</strong><span class="xs muted">이번 달 {{ won(total.apiMonth) }}</span></div>
        <div v-if="total.budget"><span class="xs muted">API 월 예산 대비</span><strong>{{ pct(total.apiMonth, total.budget) }}%</strong><span class="xs muted">월 예산 {{ won(total.budget) }}</span></div>
      </div>

      <div class="table-wrap">
        <table class="table" style="min-width: 760px">
          <caption class="sr-only">팀별 오늘 사용량. 경보 좌석이 많고 소비가 빠른 팀부터</caption>
          <thead><tr>
            <th scope="col">팀</th><th scope="col" class="num">인원</th><th scope="col" class="num">좌석 토큰 오늘</th>
            <th scope="col">소비 속도 (팀 평균 대비)</th><th scope="col" class="num">API 오늘</th><th scope="col">API 이번 달 / 월 예산</th>
          </tr></thead>
          <tbody>
            <tr v-for="t in teams" :key="t.dept_id">
              <th scope="row"><button type="button" class="team" @click="emit('pick', t.dept_id)">{{ t.dept_name }}<span class="sr-only"> 구역을 배치도에서 보기</span></button></th>
              <td class="num">{{ t.headcount }}명</td>
              <td class="num">
                <template v-if="t.seats_tracked">{{ n(t.tokens_today) }}<br /><span class="xs muted">좌석 {{ t.seats_tracked }}석 · 예상 {{ n(t.projected_today) }}</span></template>
                <span v-else class="muted">토큰 좌석 없음</span>
              </td>
              <td>
                <span v-if="t.seats_tracked && !t.tokens_today" class="muted">오늘 사용 없음</span>
                <div v-else-if="t.seats_tracked" class="bar-inline">
                  <div class="bar" role="img" :aria-label="`팀 평균의 ${t.ratio}배`"><div :class="{ hot: t.ratio >= 2 }" :style="{ width: `${Math.min(100, (t.ratio / RATIO_FULL) * 100)}%` }" /></div>
                  <span class="nowrap">{{ t.ratio }}배 · {{ pace(t) }}</span>
                </div>
                <span v-if="t.seats_over || t.seats_caution" class="xs">
                  <span v-if="t.seats_over" class="pill pill-alert">2배 이상 {{ t.seats_over }}석</span>
                  <span v-if="t.seats_caution" class="xs muted"> 빠름 {{ t.seats_caution }}석</span>
                </span>
              </td>
              <td class="num">{{ t.api_cost_today_krw ? won(t.api_cost_today_krw) : '-' }}<br /><span v-if="t.api_requests_today" class="xs muted">{{ n(t.api_requests_today) }}건</span></td>
              <td>
                <div v-if="t.api_budget_month_krw" class="bar-inline">
                  <div class="bar" role="img" :aria-label="`월 예산의 ${pct(t.api_cost_month_krw, t.api_budget_month_krw)}%`"><div :class="{ hot: t.api_cost_month_krw > t.api_budget_month_krw }" :style="{ width: `${Math.min(100, pct(t.api_cost_month_krw, t.api_budget_month_krw))}%` }" /></div>
                  <span class="nowrap small">{{ won(t.api_cost_month_krw) }} / {{ won(t.api_budget_month_krw) }}</span>
                </div>
                <span v-else-if="t.api_cost_month_krw" class="small">{{ won(t.api_cost_month_krw) }} <span class="xs muted">예산 없음</span></span>
                <span v-else class="muted">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="xs muted" style="margin: 0">소비 속도 = 팀 좌석들의 오늘 예상 합 ÷ 같은 좌석들의 평균 하루 사용량 합 (근무 9–18시 기준). 막대 끝은 {{ RATIO_FULL }}배. 이용권 관리에만 쓰고 인사평가에 쓰지 않습니다.</p>
    </template>
  </section>
</template>

<style scoped>
.sum { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.sum div { display: flex; flex-direction: column; gap: 2px; padding: 12px 14px; border-radius: 12px; background: var(--paper); }
.sum strong { font-size: 22px; letter-spacing: -0.02em; }
.team { min-height: 36px; padding: 0; border: 0; background: none; font-weight: 700; text-align: left; text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--line-strong); }
.team:hover { text-decoration-color: var(--ink); }
.table th[scope='row'] { font-size: 14px; color: var(--ink); padding: 14px 12px 14px 0; border-top: 1px solid var(--line); }
.bar-inline .bar { width: 90px; }
.bar .hot { background: var(--lime); outline: 1px solid var(--ink); }
.pill { margin-top: 6px; }
</style>
