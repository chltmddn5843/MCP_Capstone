<script setup>
// 팀별 오늘 사용량 (GET /usage/teams). 좌석 토큰은 좌석 배치도와 같은 소비 속도 기준을 팀으로 합친 것, API는 팀 프로젝트 비용. 30초마다 갱신.
// 확인이 필요한 팀이 맨 위에 온다 (2배 이상 좌석 > API 예산 초과 > 빠름 좌석 > 이용권 확인). 팀 이름을 누르면 배치도가 그 구역으로 가고(pick),
// 경보 좌석·이용권 확인 직원을 누르면 그 자리를 바로 고른다(pick-seat). 이용권 확인 명단(checks)은 배치도가 /org/members에서 만들어 넘긴다.
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getTeamUsage } from '../api.js'
import { won, pct } from '../labels.js'
import { teamBadge } from '../insight.js'

const props = defineProps({ checks: { type: Object, default: () => ({}) } }) // dept_id → [{ id, name, label }]
const emit = defineEmits(['pick', 'pick-seat', 'load'])
const teams = ref(null)
const at = ref('')
const failed = ref(false)
async function load() {
  try {
    teams.value = await getTeamUsage()
    at.value = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    failed.value = false
    emit('load', teams.value)
  } catch { failed.value = true } // 이전 값은 그대로 두고 '갱신 실패'만 알린다
}
let timer
onMounted(() => { load(); timer = setInterval(load, 30000) })
onUnmounted(() => clearInterval(timer))
defineExpose({ reload: load })

const n = (v) => Math.round(v).toLocaleString('ko-KR')
const sum = (k) => (teams.value ?? []).reduce((s, t) => s + t[k], 0)
const total = computed(() => teams.value && {
  tokens: sum('tokens_today'), projected: sum('projected_today'), over: sum('seats_over'), caution: sum('seats_caution'),
  apiToday: sum('api_cost_today_krw'), apiMonth: sum('api_cost_month_krw'), budget: sum('api_budget_month_krw'),
  checks: Object.values(props.checks).reduce((s, l) => s + l.length, 0),
})
const RATIO_FULL = 2.5 // 막대 끝 = 평균의 2.5배
const pace = (t) => (!t.seats_tracked ? '' : t.ratio >= 2 ? '2배 이상' : t.ratio >= 1.5 ? '빠름' : '보통')
const apiOver = (t) => !!t.api_budget_month_krw && t.api_cost_month_krw > t.api_budget_month_krw
const badge = (t) => teamBadge({ over: t.seats_over, caution: t.seats_caution, checks: (props.checks[t.dept_id] ?? []).length, apiOver: apiOver(t) })
// 배지 우선순위 → 서버 정렬(2배 이상 좌석 수 → 배수 → API 비용) 순
const rows = computed(() => (teams.value ?? []).map((t, i) => ({ t, i, badge: badge(t) })).sort((a, b) => (b.badge?.rank ?? 0) - (a.badge?.rank ?? 0) || a.i - b.i))
const PACE = { over: '2배 이상', caution: '빠름' }
// 팀 한 줄에서 바로 고를 자리: 경보 좌석(배수 높은 순) + 이용권 확인 직원. 같은 사람은 한 번만
const picks = (t) => {
  const out = t.alert_seats.map((s) => ({ id: s.employee_id, name: s.employee_name, label: `×${s.ratio}`, tone: s.level === 'over' ? 'alert' : 'ok', title: `${s.product} · 오늘 예상 ${n(s.projected_today)} 토큰 · ${PACE[s.level]}` }))
  for (const c of props.checks[t.dept_id] ?? []) if (!out.some((x) => x.id === c.id)) out.push({ id: c.id, name: c.name, label: c.label, tone: 'neutral', title: `이용권 확인 · ${c.label}` })
  return out
}
</script>

<template>
  <section class="card" aria-labelledby="tu-h">
    <div class="card-head">
      <div>
        <h2 id="tu-h">팀별 실시간 사용량</h2>
        <span class="small muted">오늘 기준 · 30초마다 갱신<template v-if="at"> · 마지막 {{ at }}</template><template v-if="failed"> · 갱신 실패, 이전 값을 보여 줍니다</template> · 확인이 필요한 팀이 맨 위</span>
      </div>
    </div>

    <p v-if="!teams" class="small muted loading" aria-busy="true">팀별 사용량을 불러오는 중…</p>
    <p v-else-if="!teams.length" class="small muted loading">아직 사용 기록이 있는 팀이 없습니다.</p>
    <template v-else>
      <div class="sum">
        <div><span class="xs muted">좌석 토큰 오늘</span><strong>{{ n(total.tokens) }}</strong><span class="xs muted">이 속도면 {{ n(total.projected) }}</span></div>
        <div><span class="xs muted">소비 경보 좌석</span><strong>{{ total.over }}석</strong><span class="xs muted">2배 이상 · 빠름 {{ total.caution }}석</span></div>
        <div><span class="xs muted">이용권 확인</span><strong>{{ total.checks }}명</strong><span class="xs muted">장기 미사용·휴직 등</span></div>
        <div><span class="xs muted">API 비용 오늘</span><strong>{{ won(total.apiToday) }}</strong><span class="xs muted">이번 달 {{ won(total.apiMonth) }}</span></div>
        <div v-if="total.budget"><span class="xs muted">API 월 예산 대비</span><strong>{{ pct(total.apiMonth, total.budget) }}%</strong><span class="xs muted">월 예산 {{ won(total.budget) }}</span></div>
      </div>

      <div class="table-wrap">
        <table class="table" style="min-width: 880px">
          <caption class="sr-only">팀별 오늘 사용량. 확인이 필요한 팀부터</caption>
          <thead><tr>
            <th scope="col">팀</th><th scope="col">확인</th><th scope="col" class="num">인원</th><th scope="col" class="num">좌석 토큰 오늘</th>
            <th scope="col">소비 속도 (팀 평균 대비)</th><th scope="col" class="num">API 오늘</th><th scope="col">API 이번 달 / 월 예산</th>
          </tr></thead>
          <tbody>
            <tr v-for="{ t, badge: b } in rows" :key="t.dept_id" :class="{ flagged: b }">
              <th scope="row">
                <button type="button" class="team" @click="emit('pick', t.dept_id)">{{ t.dept_name }}<span class="sr-only"> 구역을 배치도에서 보기</span></button>
                <div v-if="picks(t).length" class="picks" role="group" :aria-label="`${t.dept_name} 확인이 필요한 자리`">
                  <button v-for="p in picks(t)" :key="p.id" type="button" class="seat-chip" :class="`tone-${p.tone}`" :title="p.title" @click="emit('pick-seat', p.id)">
                    {{ p.name }} <b>{{ p.label }}</b><span class="sr-only"> · {{ p.title }} · 자리 보기</span>
                  </button>
                </div>
              </th>
              <td><span v-if="b" class="pill" :class="`pill-${b.tone}`">{{ b.label }}</span><span v-else class="xs muted">-</span></td>
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
              </td>
              <td class="num">{{ t.api_cost_today_krw ? won(t.api_cost_today_krw) : '-' }}<br /><span v-if="t.api_requests_today" class="xs muted">{{ n(t.api_requests_today) }}건</span></td>
              <td>
                <div v-if="t.api_budget_month_krw" class="bar-inline">
                  <div class="bar" role="img" :aria-label="`월 예산의 ${pct(t.api_cost_month_krw, t.api_budget_month_krw)}%`"><div :class="{ hot: apiOver(t) }" :style="{ width: `${Math.min(100, pct(t.api_cost_month_krw, t.api_budget_month_krw))}%` }" /></div>
                  <span class="nowrap small">{{ won(t.api_cost_month_krw) }} / {{ won(t.api_budget_month_krw) }}</span>
                </div>
                <span v-else-if="t.api_cost_month_krw" class="small">{{ won(t.api_cost_month_krw) }} <span class="xs muted">예산 없음</span></span>
                <span v-else class="muted">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="xs muted" style="margin: 0">소비 속도 = 팀 좌석들의 오늘 예상 합 ÷ 같은 좌석들의 평균 하루 사용량 합 (근무 9–18시 기준). 막대 끝은 {{ RATIO_FULL }}배. 팀 이름을 누르면 아래 배치도가 그 구역으로, 이름 칩을 누르면 그 자리의 이유·해결책이 열립니다. 이용권 관리에만 쓰고 인사평가에 쓰지 않습니다.</p>
    </template>
  </section>
</template>

<style scoped>
.sum { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.sum div { display: flex; flex-direction: column; gap: 2px; padding: 12px 14px; border-radius: 12px; background: var(--paper); }
.sum strong { font-size: 22px; letter-spacing: -0.02em; }
.team { min-height: 36px; padding: 0; border: 0; background: none; font-weight: 700; text-align: left; text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--line-strong); }
.team:hover { text-decoration-color: var(--ink); }
.table th[scope='row'] { font-size: 14px; color: var(--ink); padding: 14px 12px 14px 0; border-top: 1px solid var(--line); vertical-align: top; }
.table tr.flagged th[scope='row'] { box-shadow: inset 3px 0 0 var(--ink); padding-left: 10px; }
.picks { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.seat-chip { min-height: 28px; padding: 0 10px; border-radius: 999px; border: 1px solid var(--line-strong); background: var(--white); font-size: 12px; font-weight: 500; display: inline-flex; align-items: center; gap: 4px; }
.seat-chip:hover { border-color: var(--ink); }
.seat-chip.tone-alert { background: var(--lime); border: 1px solid var(--ink); }
.seat-chip.tone-ok { background: rgba(220, 239, 109, 0.45); }
.seat-chip.tone-neutral { border-style: dashed; }
.bar-inline .bar { width: 90px; }
.bar .hot { background: var(--lime); outline: 1px solid var(--ink); }
</style>
