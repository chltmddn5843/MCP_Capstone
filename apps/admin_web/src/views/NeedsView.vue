<script setup>
// 활용 지원 › 미지원 요청: 추후 개발 자리. 10/22 기능 개편(설계문서 결정 8)으로 기록·도구·화면을 뺐고, 지금은 아무것도 기록하지 않는다.
// 직원이 승인 제품으로 할 수 없는 기능을 물으면 AI 비서는 "지금 승인된 제품으로는 어렵습니다"라고만 답한다.
// 이 화면은 다시 넣을 때의 모양(와이어프레임)을 예시 데이터로 보여 준다. 모든 숫자·이름은 예시이고 실행 버튼은 비활성이다.
import { ref, computed } from 'vue'

const MET = { count: 3, depts: 2 } // 설계문서 D-2: 같은 기능 3건 이상 · 2개 부서 이상이면 검토 기준 충족
const SAMPLE = [
  { id: 'n1', feature: '계약서 조항 비교', count: 5, depts: ['영업', '경영지원'], last: '10/22', asked: ['ChatGPT Enterprise', 'Acrobat Pro'], note: '두 계약서의 달라진 조항만 뽑아 달라는 요청. 승인 제품에 문서 비교 기능 없음' },
  { id: 'n2', feature: '회의 녹음 요약', count: 3, depts: ['마케팅', 'HRD'], last: '10/21', asked: ['ChatGPT Enterprise'], note: '녹음 파일을 올려 회의록으로. 음성 입력은 승인 플랜에서 꺼져 있음' },
  { id: 'n3', feature: '이미지 배경 제거', count: 2, depts: ['상품기획·MD'], last: '10/20', asked: ['Canva Enterprise'], note: '상품 사진 배경 제거. Canva 플랜 업그레이드 필요' },
  { id: 'n4', feature: '엑셀 수식 자동 생성', count: 1, depts: ['생산관리'], last: '10/17', asked: ['ChatGPT Enterprise'], note: '생산 일정표 수식. 승인 제품으로 가능한데 사용법을 모름 → 활용 제안 후보' },
]
const met = (n) => n.count >= MET.count && n.depts.length >= MET.depts
const selId = ref(SAMPLE[0].id)
const sel = computed(() => SAMPLE.find((n) => n.id === selId.value))
const total = computed(() => ({ requests: SAMPLE.reduce((s, n) => s + n.count, 0), met: SAMPLE.filter(met).length, depts: new Set(SAMPLE.flatMap((n) => n.depts)).size }))
const PLAN = [
  { title: '기록', body: '직원이 승인 제품으로 할 수 없는 기능을 물으면 AI 비서가 기능·부서·시점을 기록합니다. 대화 내용은 남기지 않습니다.' },
  { title: '집계', body: `같은 기능이 ${MET.count}건 이상, ${MET.depts}개 부서 이상에서 나오면 "검토 기준 충족"으로 표시합니다.` },
  { title: '검토', body: '기준을 충족한 기능은 승인 제품·플랜의 업데이트와 대조해, 이미 생긴 기능이면 활용 제안으로, 없으면 구매 검토 요청으로 이어집니다.' },
]
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">활용 지원 · 추후 개발 · 아래는 예시 데이터</span><h1>미지원 요청</h1></div>
    <span class="pill pill-neutral">아직 기록하지 않음</span>
  </header>

  <p class="status" role="status" style="margin: 0">이 화면은 추후 개발 자리입니다. 10/22 개편에서 미지원 요청 기록을 뺐고, 지금은 직원이 승인 제품으로 할 수 없는 기능을 물어도 어디에도 남기지 않습니다. 아래 숫자·이름은 모양을 보여 주기 위한 예시입니다.</p>

  <section class="kpis" aria-label="미지원 요청 요약 (예시)">
    <div class="card-dark kpi"><span class="small muted">최근 30일 요청</span><span class="value">{{ total.requests }}건</span><span class="xs muted">기능 {{ SAMPLE.length }}가지 · 부서 {{ total.depts }}곳</span></div>
    <div class="card-lime kpi"><span class="small">검토 기준 충족</span><span class="value">{{ total.met }}건</span><span class="xs">같은 기능 {{ MET.count }}건 이상 · {{ MET.depts }}개 부서 이상</span></div>
    <div class="card kpi"><span class="small muted">활용 제안으로 돌린 것</span><span class="value">1건</span><span class="xs muted">승인 제품으로 가능했던 요청</span></div>
    <div class="card kpi"><span class="small muted">구매 검토로 올린 것</span><span class="value">0건</span><span class="xs muted">승인 대기로 들어감</span></div>
  </section>

  <div class="row">
    <section class="card col-3" aria-labelledby="need-h">
      <div class="card-head">
        <div><h2 id="need-h">미지원 요청 (최근 30일)</h2><span class="small muted">승인 제품으로 할 수 없었던 직원 요청 · 많이 나온 기능부터 · 예시</span></div>
        <span class="pill pill-neutral">예시 데이터</span>
      </div>
      <div class="table-wrap">
        <table class="table" style="min-width: 640px">
          <thead><tr><th scope="col">요청한 기능</th><th scope="col" class="num">요청 수</th><th scope="col">요청 부서</th><th scope="col">최근 요청</th><th scope="col">검토 기준</th></tr></thead>
          <tbody>
            <tr v-for="n in SAMPLE" :key="n.id" :class="{ picked: n.id === selId }">
              <th scope="row"><button type="button" class="feat" :aria-pressed="n.id === selId" @click="selId = n.id">{{ n.feature }}</button></th>
              <td class="num">{{ n.count }}건</td>
              <td><span v-for="d in n.depts" :key="d" class="chip chip-sm">{{ d }}</span></td>
              <td class="small muted">{{ n.last }}</td>
              <td><span class="pill" :class="met(n) ? 'pill-alert' : 'pill-neutral'">{{ met(n) ? '충족' : `${n.count}/${MET.count}건 · ${n.depts.length}/${MET.depts}부서` }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <aside class="card col-1 detail" aria-labelledby="sel-h">
      <h2 id="sel-h">{{ sel.feature }}</h2>
      <span class="pill" :class="met(sel) ? 'pill-alert' : 'pill-neutral'" style="align-self: flex-start">{{ met(sel) ? '검토 기준 충족' : '아직 기준 미달' }}</span>
      <dl class="facts">
        <div><dt class="xs muted">요청</dt><dd>{{ sel.count }}건 · {{ sel.depts.join(', ') }}</dd></div>
        <div><dt class="xs muted">직원이 써 본 제품</dt><dd>{{ sel.asked.join(', ') }}</dd></div>
        <div><dt class="xs muted">요약</dt><dd class="small">{{ sel.note }}</dd></div>
      </dl>
      <h3 class="small">할 일 (추후)</h3>
      <div class="tags" style="gap: 8px">
        <button type="button" class="btn btn-sm btn-dark" disabled title="추후 개발">업데이트와 대조</button>
        <button type="button" class="btn btn-sm" disabled title="추후 개발">활용 제안으로</button>
        <button type="button" class="btn btn-sm" disabled title="추후 개발">구매 검토 요청</button>
      </div>
      <span class="xs muted">버튼은 기능이 들어오면 켜집니다.</span>
    </aside>
  </div>

  <section class="card" aria-labelledby="plan-h">
    <h2 id="plan-h">들어올 흐름</h2>
    <ol class="plan">
      <li v-for="(p, i) in PLAN" :key="p.title"><span class="step">{{ i + 1 }}</span><div class="cell-2"><span>{{ p.title }}</span><span>{{ p.body }}</span></div></li>
    </ol>
    <p class="xs muted" style="margin: 0">팀별 활용 현황(제안 반응)은 자동 제안 기록과 팀별 사용량 화면에 있습니다.</p>
  </section>
</template>

<style scoped>
.feat { padding: 0; border: 0; background: none; font-weight: 700; font-size: 14px; text-align: left; text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--line-strong); min-height: 36px; }
.feat:hover, .feat[aria-pressed='true'] { text-decoration-color: var(--ink); }
.table th[scope='row'] { padding: 10px 12px 10px 0; border-top: 1px solid var(--line); }
tr.picked td, tr.picked th { background: var(--paper); }
.chip-sm { min-height: 26px; padding: 0 10px; font-size: 12px; margin-right: 4px; }
.detail { position: sticky; top: 24px; gap: 12px; }
.facts { margin: 0; display: flex; flex-direction: column; gap: 8px; }
.facts div { display: flex; flex-direction: column; gap: 2px; }
.facts dd { margin: 0; }
.plan { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; }
.plan li { display: flex; align-items: flex-start; gap: 14px; padding: 12px 0; border-top: 1px solid var(--line); }
.plan .cell-2 > :last-child { font-size: 13px; line-height: 1.5; }
.step { width: 28px; height: 28px; border-radius: 999px; background: var(--ink); color: var(--lime); font-weight: 700; font-size: 13px; display: grid; place-items: center; flex: none; }
@media (max-width: 900px) { .detail { position: static; } }
</style>
