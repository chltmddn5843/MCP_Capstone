<script setup>
// 활용 지원 › 미지원 요청: 추후 개발 자리. 10/22 기능 개편(설계문서 결정 8)으로 기록·도구·화면을 뺐고, 지금은 아무것도 기록하지 않는다.
// 직원이 승인 제품으로 할 수 없는 기능을 물으면 AI 비서는 "지금 승인된 제품으로는 어렵습니다"라고만 답한다. 이 화면은 그 자리를 남겨 두고 무엇이 들어올지 보여 준다.
const COLS = ['요청한 기능', '요청 수', '요청 부서', '최근 요청', '검토 기준']
const PLAN = [
  { title: '기록', body: '직원이 승인 제품으로 할 수 없는 기능을 물으면 AI 비서가 기능·부서·시점을 기록합니다. 대화 내용은 남기지 않습니다.' },
  { title: '집계', body: '같은 기능이 3건 이상, 2개 부서 이상에서 나오면 "검토 기준 충족"으로 표시합니다.' },
  { title: '검토', body: '기준을 충족한 기능은 승인 제품·플랜의 업데이트와 대조해, 이미 생긴 기능이면 활용 제안으로, 없으면 구매 검토 요청으로 이어집니다.' },
]
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">활용 지원 · 추후 개발</span><h1>미지원 요청</h1></div>
    <span class="pill pill-neutral">아직 기록하지 않음</span>
  </header>

  <section class="card-lime" aria-labelledby="soon-h">
    <h2 id="soon-h">이 화면은 추후 개발 예정입니다</h2>
    <p class="small" style="margin: 0; line-height: 1.6">10/22 기능 개편에서 미지원 요청 기록을 뺐습니다. 지금은 직원이 승인 제품으로 할 수 없는 기능을 물어도 AI 비서가 "지금 승인된 제품으로는 어렵습니다"라고 답할 뿐, 어디에도 남기지 않습니다. 아래는 다시 넣을 때의 모양입니다.</p>
  </section>

  <section class="card" aria-labelledby="need-h">
    <div class="card-head">
      <div><h2 id="need-h">미지원 요청 (최근 30일)</h2><span class="small muted">승인 제품으로 할 수 없었던 직원 요청 · 같은 기능 3건 이상, 2개 부서 이상이면 검토 기준 충족</span></div>
    </div>
    <div class="table-wrap">
      <table class="table" style="min-width: 640px" aria-describedby="need-empty">
        <thead><tr><th v-for="c in COLS" :key="c" scope="col">{{ c }}</th></tr></thead>
        <tbody><tr><td :colspan="COLS.length" id="need-empty" class="muted small" style="padding: 28px 0; text-align: center">아직 기록하지 않습니다. 기능이 들어오면 여기에 쌓입니다.</td></tr></tbody>
      </table>
    </div>
  </section>

  <section class="card" aria-labelledby="plan-h">
    <h2 id="plan-h">들어올 흐름</h2>
    <ol class="plan">
      <li v-for="(p, i) in PLAN" :key="p.title"><span class="step">{{ i + 1 }}</span><div class="cell-2"><span>{{ p.title }}</span><span>{{ p.body }}</span></div></li>
    </ol>
    <p class="xs muted" style="margin: 0">팀별 활용 현황(제안 반응)은 자동 제안 기록과 팀별 사용량 화면에 있습니다.</p>
  </section>
</template>

<style scoped>
.plan { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; }
.plan li { display: flex; align-items: flex-start; gap: 14px; padding: 12px 0; border-top: 1px solid var(--line); }
.plan .cell-2 > :last-child { font-size: 13px; line-height: 1.5; }
.step { width: 28px; height: 28px; border-radius: 999px; background: var(--ink); color: var(--lime); font-weight: 700; font-size: 13px; display: grid; place-items: center; flex: none; }
</style>
