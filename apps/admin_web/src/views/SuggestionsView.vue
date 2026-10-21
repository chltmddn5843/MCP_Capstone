<script setup>
import { ref, onMounted } from 'vue'
import { getUpdates, getSuggestionStats, getTeamSwitches, setTeamSwitch } from '../api.js'
import { SEND_RESULT } from '../labels.js'

const updates = ref([])
const stats = ref(null)
const switches = ref([])

onMounted(async () => {
  ;[updates.value, stats.value, switches.value] = await Promise.all([getUpdates(), getSuggestionStats(), getTeamSwitches()])
})

const toggle = (t) => setTeamSwitch(t.id, t.enabled)
const sentCount = (u) => u.teams.filter((t) => t.result === 'sent').length
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">활용 지원 · F1 · 업데이트 주 1회 수집<template v-if="stats"> (다음 {{ stats.nextRun }})</template></span><h1>자동 제안 기록</h1></div>
  </header>

  <section v-if="stats" class="kpis" aria-label="이번 주 요약">
    <div class="card kpi"><span class="small muted">수집한 업데이트</span><span class="value">{{ stats.collected }}건</span></div>
    <div class="card-dark kpi"><span class="small muted">팀에 보낸 제안</span><span class="value" style="color: var(--lime)">{{ stats.sent }}건</span></div>
    <div class="card kpi"><span class="small muted">보내지 않음</span><span class="value">{{ stats.held }}건</span></div>
    <div class="card kpi"><span class="small muted">도움 됨 반응</span><span class="value">{{ stats.helpfulRate }}%</span></div>
  </section>

  <div class="row">
    <section class="col-3 stack" style="gap: 12px" aria-labelledby="upd-h">
      <h2 id="upd-h">업데이트별 판단</h2>
      <article v-for="u in updates" :key="u.id" class="card">
        <div class="card-head" style="align-items: flex-start">
          <div>
            <span class="xs muted">{{ u.product }} · 릴리스 노트 {{ u.date }}</span>
            <h3>{{ u.title }}</h3>
            <span v-if="u.note" class="small">{{ u.note }}</span>
          </div>
          <a v-if="u.sourceUrl" :href="u.sourceUrl" class="small" style="font-weight: 600">공식 원문</a>
          <span v-else class="pill" :class="u.result === 'sent' ? 'pill-ok' : 'pill-alert'">{{ u.result === 'sent' ? '보냄' : '보류' }}</span>
        </div>
        <div v-if="u.teams.length" class="table-wrap">
          <table class="table" style="min-width: 560px">
            <caption class="sr-only">{{ u.title }} 팀별 결과 · 보낸 팀 {{ sentCount(u) }}곳</caption>
            <thead><tr><th scope="col">팀</th><th scope="col">결과</th><th scope="col">판단 근거 / 사유</th><th scope="col">반응</th></tr></thead>
            <tbody>
              <tr v-for="t in u.teams" :key="t.team">
                <td style="font-weight: 600">{{ t.team }}</td>
                <td><span class="pill" :class="`pill-${SEND_RESULT[t.result].tone}`">{{ SEND_RESULT[t.result].label }}{{ t.at ? ` · ${t.at}` : '' }}</span></td>
                <td>{{ t.reason }}</td>
                <td class="nowrap" :class="{ muted: !t.reaction }">{{ t.reaction ?? '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <aside class="col-1 stack">
      <section class="card" aria-labelledby="sw-h" style="gap: 4px">
        <h2 id="sw-h">팀별 자동 발송</h2>
        <span class="small muted" style="padding-bottom: 8px">끄면 그 팀에는 보내지 않고 기록만 남깁니다.</span>
        <label v-for="t in switches" :key="t.id" class="switch-row">
          <span>{{ t.team }} <span class="xs muted">{{ t.channel }}</span></span>
          <input v-model="t.enabled" type="checkbox" role="switch" :disabled="t.readonly" :title="t.readonly ? '백엔드 PATCH /departments 연결 전' : ''" @change="toggle(t)">
        </label>
      </section>
      <section class="card-dark small" aria-label="알림 정책" style="line-height: 1.6">
        <strong style="color: var(--lime)">알림 정책 · 코드로 검사</strong>
        <span>팀당 주 2건까지</span>
        <span>평일 09:00~18:00에만 발송</span>
        <span>관련성 근거가 있는 제안만</span>
        <span>같은 분야 "관련 없음" 2회 연속이면 4주 보류</span>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 48px; border-top: 1px solid var(--line); font-size: 14px; cursor: pointer; }
.switch-row input { accent-color: var(--ink); width: 20px; height: 20px; margin: 0; }
</style>
