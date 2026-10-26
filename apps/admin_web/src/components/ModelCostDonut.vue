<script setup>
// 월별 API 모델 비용 도넛. 한 바퀴 = 월 예산(비용이 넘으면 = 비용). 조각 = 모델별 비용, 회색 = 남은 예산.
// 진행 중인 달은 '오늘까지 써야 정상인 위치'(예산 × 경과일/월 일수)에 눈금을 그려 빠르게 쓰는지 보이게 한다.
import { ref, computed } from 'vue'
import { won, pct, onTabKeys } from '../labels.js'

const props = defineProps({ months: { type: Array, required: true } })
const idx = ref(props.months.length - 1)
const m = computed(() => props.months[idx.value])

const R = 70, C = 2 * Math.PI * R, GAP = 2
const COLORS = ['var(--ink)', '#6b6b70', 'var(--lime)', '#a8a8ad'] // 4개 넘으면 '기타'로 묶는다
const total = computed(() => m.value.models.reduce((s, x) => s + x.cost, 0))
const requests = computed(() => m.value.models.reduce((s, x) => s + x.requests, 0))
const rows = computed(() => {
  const ms = m.value.models
  const list = ms.length > 4 ? [...ms.slice(0, 3), { name: '기타', cost: ms.slice(3).reduce((s, x) => s + x.cost, 0), requests: ms.slice(3).reduce((s, x) => s + x.requests, 0) }] : ms
  return list.map((x, i) => ({ ...x, color: COLORS[i], share: pct(x.cost, total.value), reqShare: pct(x.requests, requests.value) }))
})
const ring = computed(() => Math.max(m.value.budget, total.value) || 1)
const arcs = computed(() => {
  let at = 0
  const out = rows.value.map((x) => { const len = (x.cost / ring.value) * C; const a = { color: x.color, len, at }; at += len; return a })
  if (m.value.budget > total.value) out.push({ color: 'var(--track)', len: C - at, at })
  return out.filter((a) => a.len > GAP)
})
const tick = (amount) => { const t = (amount / ring.value) * 2 * Math.PI - Math.PI / 2; return { x1: 90 + 58 * Math.cos(t), y1: 90 + 58 * Math.sin(t), x2: 90 + 84 * Math.cos(t), y2: 90 + 84 * Math.sin(t) } }
const pace = computed(() => (m.value.ongoing ? Math.round((m.value.budget * m.value.elapsed) / m.value.monthDays) : null))
// 진행 중인 달 월말 예상: 데이터가 있는 날 평균 × 월 일수
const projected = computed(() => (m.value.ongoing && m.value.dataDays ? Math.round((total.value / m.value.dataDays) * m.value.monthDays) : null))
const partial = computed(() => !m.value.ongoing && m.value.dataDays && m.value.dataDays < m.value.monthDays)
const over = computed(() => total.value > m.value.budget)
const top = computed(() => rows.value[0])
const xCost = (x) => x.models.reduce((s, row) => s + row.cost, 0)
const xRequests = (x) => x.models.reduce((s, row) => s + row.requests, 0)
const maxCost = computed(() => Math.max(...props.months.map(xCost), 1))
const barHeight = (x) => Math.max(4, Math.round((xCost(x) / maxCost.value) * 100))
const trendSummary = computed(() => props.months.map((x) => `${x.label} ${won(xCost(x))}, ${xRequests(x)}건`).join('; '))
const summary = computed(() => `${m.value.label} API 비용 ${won(total.value)}, 월 예산 ${won(m.value.budget)}의 ${pct(total.value, m.value.budget)}%. `
  + rows.value.map((x) => `${x.name} ${won(x.cost)} ${x.share}%`).join(', '))
</script>

<template>
  <section class="card" aria-labelledby="mc-h">
    <div class="card-head">
      <div>
        <h2 id="mc-h">모델별 API 비용 · 예산 대비</h2>
        <span class="small muted">API 사용량 과금만 · 좌석 정액료는 모델과 무관해 제외</span>
      </div>
      <div role="tablist" aria-label="월" class="segment" @keydown="onTabKeys">
        <button v-for="(x, i) in months" :key="x.label" type="button" role="tab" :aria-selected="i === idx" :tabindex="i === idx ? 0 : -1" @click="idx = i">{{ x.label }}{{ x.ongoing ? ' · 진행 중' : '' }}</button>
      </div>
    </div>

    <p v-if="!m.models.length" class="small muted" style="margin: 0">{{ m.label }}에는 API 사용 기록이 없습니다.</p>
    <div v-else class="body">
      <figure class="donut">
        <svg viewBox="0 0 180 180" width="180" height="180" role="img" :aria-label="summary">
          <circle v-for="(a, i) in arcs" :key="i" cx="90" cy="90" :r="R" fill="none" :stroke="a.color" stroke-width="22"
            :stroke-dasharray="`${a.len - GAP} ${C}`" :stroke-dashoffset="-a.at" transform="rotate(-90 90 90)" />
          <line v-if="over" v-bind="tick(m.budget)" class="mark" />
          <line v-if="pace" v-bind="tick(pace)" class="mark dashed" />
        </svg>
        <figcaption>
          <strong :class="{ over }">{{ pct(total, m.budget) }}%</strong>
          <span class="xs muted">예산 대비</span>
        </figcaption>
      </figure>

      <div class="side">
        <div class="nums">
          <div><span class="xs muted">{{ m.ongoing ? `${m.elapsed}일까지 누계` : '월 합계' }}</span><strong>{{ won(total) }}</strong></div>
          <div><span class="xs muted">월 예산</span><strong>{{ won(m.budget) }}</strong></div>
          <div v-if="projected"><span class="xs muted">월말 예상</span><strong :class="{ over: projected > m.budget }">{{ won(projected) }}</strong></div>
        </div>
        <ul class="rows">
          <li v-for="x in rows" :key="x.name">
            <i class="swatch" :style="{ background: x.color }" />
            <span class="name">{{ x.name }}</span>
            <span class="num">{{ won(x.cost) }}</span>
            <span class="num strong">{{ x.share }}%</span>
          </li>
          <li v-if="!over" class="muted"><i class="swatch" style="background: var(--track)" /><span class="name">남은 예산</span><span class="num">{{ won(m.budget - total) }}</span><span class="num" /></li>
        </ul>
        <div class="legend">
          <span v-if="pace"><i class="tick dashed" />오늘까지 정상 사용 위치 {{ won(pace) }}</span>
          <span v-if="over"><i class="tick" />예산선 · {{ won(total - m.budget) }} 초과</span>
        </div>
      </div>
    </div>

    <div v-if="months.length > 1" class="trend">
      <div class="card-head">
        <div><h3>월별 API 비용 추이</h3><span class="small muted">현재 컬럼 기준: 비용 · 요청 수</span></div>
        <span class="small muted">최대 {{ won(maxCost) }}</span>
      </div>
      <div class="trend-chart" role="img" :aria-label="trendSummary">
        <div v-for="x in months" :key="x.label" class="trend-column">
          <span class="trend-value">{{ won(xCost(x)) }}</span>
          <div class="trend-track">
            <div class="trend-bar" :style="{ height: `${barHeight(x)}%` }" />
          </div>
          <strong>{{ x.label }}</strong>
          <span class="xs muted">{{ xRequests(x).toLocaleString('ko-KR') }}건</span>
        </div>
      </div>
    </div>

    <div v-if="top" class="inset insight">
      <span class="small"><strong>{{ top.name }}</strong> 모델이 비용의 <strong>{{ top.share }}%</strong>를 차지합니다 (요청 수로는 {{ top.reqShare }}%).
        <template v-if="top.share - top.reqShare >= 10"> 요청 비중보다 비용 비중이 커서 요청당 단가가 높은 모델입니다. 품질 기준을 통과하는 하위 모델이 있는지 검토할 만합니다.</template>
      </span>
      <RouterLink v-if="top.share - top.reqShare >= 10" class="btn btn-sm" :to="{ path: '/assistant', query: { q: `${top.name} 모델을 쓰는 프로젝트 중 품질 기준을 통과하는 더 저렴한 모델로 바꿀 수 있는 것이 있는지 검토해줘` } }">AI 비서에게 모델 검토 요청</RouterLink>
    </div>
    <p v-if="partial" class="xs muted" style="margin: 0">{{ m.firstDay }}부터 수집해 {{ m.dataDays }}일치만 있습니다. 이 달의 예산 비교는 참고용입니다.</p>
    <p class="xs muted" style="margin: 0">{{ m.budgetSource === 'annual' ? `예산은 API 연간 예산 ÷ 12입니다. 프로젝트에 배분한 월 예산 합은 ${won(m.allocated)}입니다.` : '연간 예산을 설정하지 않아 API 프로젝트 월 예산의 합을 예산으로 씁니다.' }}</p>
  </section>
</template>

<style scoped>
.segment { display: flex; flex-direction: row; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 12px; background: var(--paper); }
.segment button { min-height: 36px; padding: 0 12px; border: 0; border-radius: 8px; background: transparent; font-size: 13px; }
.segment button[aria-selected='true'] { background: var(--ink); color: var(--white); font-weight: 600; }
.card-head > .segment { flex-direction: row; }
.body { display: flex; flex-wrap: wrap; align-items: center; gap: 24px; }
.trend { display: flex; flex-direction: column; gap: 14px; padding-top: 8px; border-top: 1px solid var(--line); }
.trend-chart { display: grid; grid-template-columns: repeat(auto-fit, minmax(72px, 1fr)); gap: 14px; align-items: end; min-height: 190px; }
.trend-column { min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 5px; font-size: 13px; }
.trend-value { font-size: 12px; color: var(--muted); white-space: nowrap; }
.trend-track { width: min(56px, 100%); height: 110px; display: flex; align-items: end; background: var(--track); border-radius: 8px 8px 3px 3px; overflow: hidden; }
.trend-bar { width: 100%; min-height: 4px; background: var(--ink); border-radius: 8px 8px 3px 3px; }
.trend-column:nth-child(odd) .trend-bar { background: var(--lime); }
.donut { position: relative; margin: 0; width: 180px; height: 180px; flex: none; }
.donut figcaption { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.donut figcaption strong { font-size: 30px; letter-spacing: -0.02em; }
.mark { stroke: var(--ink); stroke-width: 3; stroke-linecap: round; }
.mark.dashed { stroke-width: 2; stroke-dasharray: 3 3; }
.over { text-decoration: underline; text-decoration-thickness: 3px; text-decoration-color: var(--lime); }
.side { flex: 1 1 240px; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.nums { display: flex; flex-wrap: wrap; gap: 20px; }
.nums div { display: flex; flex-direction: column; gap: 2px; }
.nums strong { font-size: 18px; }
.rows { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; font-size: 14px; }
.rows li { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto 44px; align-items: center; gap: 10px; }
.rows .swatch { outline: 1px solid var(--line-strong); }
.num { text-align: right; }
.strong { font-weight: 700; }
.tick { width: 14px; border-top: 3px solid var(--ink); display: inline-block; }
.tick.dashed { border-top: 2px dashed var(--ink); }
.insight { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 12px; }
.insight > span { flex: 1 1 280px; line-height: 1.6; }
</style>
