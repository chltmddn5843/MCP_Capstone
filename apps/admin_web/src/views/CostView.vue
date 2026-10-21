<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getAnomalies, getProjects, createPlanFromAnomaly } from '../api.js'
import { won, pct } from '../labels.js'

const router = useRouter()
const anomalies = ref([])
const projects = ref([])
const action = ref('')
const busy = ref(false)
const CHART_H = 180

onMounted(async () => {
  ;[anomalies.value, projects.value] = await Promise.all([getAnomalies(), getProjects()])
  action.value = anomalies.value[0]?.investigation.actions[0]?.id ?? ''
})

const a = computed(() => anomalies.value[0])
const max = computed(() => Math.max(...a.value.daily, a.value.baseline))
const bars = computed(() => a.value.daily.mlap((v) => ({ v, h: (v / max.value) * CHART_H, over: v > a.value.baseline * 2 })))
const baselineY = computed(() => (a.value.baseline / max.value) * CHART_H)
const STATUS = { open: { label: '확인 전', tone: 'alert' }, investigating: { label: '처리 요청 보냄', tone: 'ok' }, resolved: { label: '처리 완료', tone: 'neutral' } }

async function submit() {
  busy.value = true
  const id = await createPlanFromAnomaly(a.value.id, action.value)
  router.push({ path: '/inbox', query: { id } })
}
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">운영 · F3 · 30분마다 수집</span><h1>비용·사용량</h1></div>
    <div class="tags" style="gap: 8px">
      <label class="field">기간
        <select><option>최근 14일</option><option>이번 달</option></select>
      </label>
      <label class="field">제품
        <select><option>Claude API</option><option>전체 제품</option></select>
      </label>
    </div>
  </header>

  <template v-if="a">
    <section class="card-dark alert" aria-label="비용 급증 알림">
      <div class="alert-main">
        <div class="tags" style="align-items: center; gap: 8px">
          <span class="pill" :class="STATUS[a.status].tone === 'alert' ? 'pill-ok' : 'pill-neutral on-ink'">비용 급증 알림 · {{ STATUS[a.status].label }}</span>
          <span class="small muted">{{ a.detectedAt }} 감지</span>
        </div>
        <strong class="alert-title">{{ a.scopeName }} 프로젝트의 하루 비용이 기준의 {{ a.ratio }}배입니다</strong>
        <span class="small muted">기준(최근 14일 평균) {{ won(a.baseline) }} → 오늘 {{ won(a.observed) }} · 이대로면 이번 달 {{ won(a.projected) }}으로 예산 {{ won(a.budget) }}을 넘습니다</span>
      </div>
      <div class="alert-nums">
        <div><span class="xs muted">이번 달 누적</span><strong>{{ won(a.monthToDate) }}</strong></div>
        <div><span class="xs muted">월 예산</span><strong>{{ won(a.budget) }}</strong></div>
      </div>
    </section>

    <div class="row">
      <div class="col-3 stack">
        <section class="card" aria-labelledby="daily-h">
          <div class="card-head">
            <div><h2 id="daily-h">{{ a.scopeName }} · 일별 비용</h2><span class="small muted">{{ a.product }} · {{ a.model }} · {{ a.env }} 환경 · 담당 {{ a.dept }}</span></div>
            <div class="legend">
              <span><i class="dash" />기준 {{ won(a.baseline) }}</span>
              <span><i class="swatch" style="background: var(--ink)" />기준 2배 초과</span>
            </div>
          </div>
          <div class="daily" role="img" :aria-label="`최근 ${a.daily.length}일 하루 비용, 마지막 날 ${won(a.observed)}, 기준 ${won(a.baseline)}`" :style="{ height: `${CHART_H + 24}px` }">
            <div class="baseline" :style="{ bottom: `${baselineY}px` }" />
            <div v-for="(b, i) in bars" :key="i" class="dbar" :class="{ over: b.over }" :style="{ height: `${b.h}px` }">
              <span v-if="b.over" class="xs dlabel">{{ b.v.toLocaleString('ko-KR') }}</span>
            </div>
          </div>
          <div class="xs muted" style="display: flex; justify-content: space-between"><span>{{ a.dailyStart }}</span><span style="color: var(--ink); font-weight: 600">오늘</span></div>
        </section>

        <section class="card" aria-labelledby="proj-h">
          <h2 id="proj-h">프로젝트별 이번 달 비용</h2>
          <div class="table-wrap">
            <table class="table" style="min-width: 620px">
              <thead><tr><th scope="col">프로젝트</th><th scope="col">모델 · 환경</th><th scope="col">예산 대비</th><th scope="col">상태</th></tr></thead>
              <tbody>
                <tr v-for="p in projects" :key="p.id">
                  <td><div class="cell-2"><span>{{ p.name }}</span><span>{{ p.dept }}</span></div></td>
                  <td>{{ p.model }} · {{ p.env }}</td>
                  <td><div class="bar-inline"><div class="bar"><div :style="{ width: `${pct(p.cost, p.budget)}%` }" /></div><span>{{ p.cost.toLocaleString('ko-KR') }} / {{ p.budget.toLocaleString('ko-KR') }}</span></div></td>
                  <td><span class="pill" :class="p.anomaly ? 'pill-alert' : 'pill-neutral'">{{ p.anomaly ? '급증' : '정상' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <aside class="card col-2" aria-labelledby="ai-h" style="gap: 18px">
        <div class="ai-head">
          <div class="ai-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" /></svg>
          </div>
          <div><h2 id="ai-h">AI 조사 결과</h2><span class="xs muted">알림 생성 시 자동 조사 · {{ a.investigation.doneAt }} 완료</span></div>
        </div>

        <div class="stack" style="gap: 10px">
          <span class="small"><strong>원인 후보</strong> <span class="muted">· 확정이 아닌 후보입니다</span></span>
          <div v-for="(c, i) in a.investigation.causes" :key="c.title" class="inset">
            <strong style="font-size: 14px">{{ i + 1 }}. {{ c.title }}</strong>
            <span class="small" style="line-height: 1.6">{{ c.body }}</span>
          </div>
        </div>

        <details class="small">
          <summary>참고한 데이터 {{ a.investigation.evidence.length }}개</summary>
          <div class="tags" style="padding-top: 8px"><span v-for="e in a.investigation.evidence" :key="e" class="tag">{{ e }}</span></div>
        </details>

        <form class="stack" style="gap: 12px" @submit.prevent="submit">
          <fieldset class="actions">
            <legend class="small"><strong>대응 선택</strong></legend>
            <label v-for="act in a.investigation.actions" :key="act.id" class="radio" :class="{ on: action === act.id }">
              <input v-model="action" type="radio" name="act" :value="act.id">{{ act.label }}
            </label>
          </fieldset>
          <div class="tags" style="gap: 8px">
            <button type="submit" class="btn btn-primary" style="flex: 1 1 160px; min-height: 48px" :disabled="busy || a.status !== 'open'">
              {{ a.status === 'open' ? '처리 요청 만들기' : '이미 처리 요청을 보냈습니다' }}
            </button>
            <button type="button" class="btn" style="min-height: 48px">AI 비서에게 더 묻기</button>
          </div>
          <span class="xs muted">만든 요청은 승인 대기로 이동합니다.</span>
        </form>
      </aside>
    </div>
  </template>
  <p v-else-if="anomalies.length === 0" class="card small muted">열린 비용 급증 알림이 없습니다.</p>
</template>

<style scoped>
.field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.field select { min-height: 44px; padding: 0 12px; border: 1px solid rgba(17, 17, 19, 0.16); border-radius: 10px; background: var(--white); color: var(--ink); font-size: 14px; }
.alert { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 24px; }
.alert-main { flex: 1 1 360px; display: flex; flex-direction: column; gap: 8px; }
.alert-title { font-size: 20px; }
.alert-nums { display: flex; gap: 24px; }
.alert-nums div { display: flex; flex-direction: column; gap: 2px; }
.alert-nums strong { font-size: 22px; }
.on-ink { color: var(--white); border-color: rgba(255, 255, 255, 0.4); }
.dash { width: 16px; border-top: 2px dashed var(--ink); display: inline-block; }
.daily { position: relative; display: flex; align-items: flex-end; gap: 8px; border-bottom: 1px solid rgba(17, 17, 19, 0.16); }
.baseline { position: absolute; left: 0; right: 0; border-top: 2px dashed rgba(17, 17, 19, 0.56); }
.dbar { flex: 1; position: relative; background: rgba(17, 17, 19, 0.12); border-radius: 4px 4px 0 0; }
.dbar.over { background: var(--ink); }
.dlabel { position: absolute; top: -20px; right: 0; font-weight: 700; white-space: nowrap; }
.ai-head { display: flex; align-items: center; gap: 10px; }
.ai-head > div:last-child { display: flex; flex-direction: column; }
.ai-icon { width: 32px; height: 32px; border-radius: 10px; background: var(--lime); display: grid; place-items: center; }
summary { cursor: pointer; font-weight: 600; min-height: 32px; display: flex; align-items: center; }
.actions { margin: 0; padding: 0; border: 0; display: flex; flex-direction: column; gap: 8px; }
.actions legend { padding-bottom: 8px; }
.radio { display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 12px; border-radius: 10px; border: 1px solid rgba(17, 17, 19, 0.16); font-size: 14px; cursor: pointer; }
.radio.on { border: 2px solid var(--ink); padding: 0 11px; }
.radio input { accent-color: var(--ink); width: 18px; height: 18px; margin: 0; }
</style>
