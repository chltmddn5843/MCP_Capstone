<script setup>
import { ref, computed, onMounted } from 'vue'
import { getUnmetNeeds, getTeamAdoption } from '../api.js'

const needs = ref([])
const adoption = ref([])
const LOW = 30 // 활용률이 이보다 낮은 팀을 '낮음'으로 표시

onMounted(async () => {
  ;[needs.value, adoption.value] = await Promise.all([getUnmetNeeds(), getTeamAdoption()])
})

// 설계 문서 D-2: 같은 기능 3건 이상 · 2개 부서 이상이면 검토 기준 충족
const meets = (n) => n.thresholdMet ?? (n.count >= 3 && n.depts.length >= 2)
const lowTeams = computed(() => adoption.value.filter((t) => t.rate < LOW))
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">활용 지원 · F5 · 매일 집계</span><h1>미지원 요청·팀 활용</h1></div>
  </header>

  <section class="card" aria-labelledby="need-h">
    <div class="card-head">
      <div>
        <h2 id="need-h">미지원 요청</h2>
        <span class="small muted">승인 제품으로 할 수 없었던 직원 요청입니다. 같은 기능 3건 이상 · 2개 부서 이상이면 검토 기준 충족.</span>
      </div>
      <span class="small muted">최근 30일</span>
    </div>
    <div v-if="needs.length" class="table-wrap">
      <table class="table" style="min-width: 640px">
        <thead><tr><th scope="col">필요한 기능</th><th scope="col" class="num">요청</th><th scope="col">부서</th><th scope="col">최근 요청 예</th><th scope="col">검토</th></tr></thead>
        <tbody>
          <tr v-for="n in needs" :key="n.capability">
            <td style="font-weight: 600">{{ n.capability }}</td>
            <td class="num" style="font-weight: 700">{{ n.count }}</td>
            <td>{{ n.deptCount != null ? `${n.deptCount}개 부서` : n.depts.join(', ') }}</td>
            <td class="muted">"{{ n.example }}"</td>
            <td><span class="pill" :class="meets(n) ? 'pill-alert' : 'pill-neutral'">{{ meets(n) ? '기준 충족' : `부서 ${n.deptCount ?? n.depts.length}개` }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="small muted">기록된 미지원 요청이 없습니다.</p>
  </section>

  <section class="card" aria-labelledby="adopt-h" style="gap: 18px">
    <div class="card-head">
      <div>
        <h2 id="adopt-h">팀별 활용 현황</h2>
        <span class="small muted">5명 이상 팀 단위로만 봅니다. 개인별 지표는 보이지 않으며 인사평가에 쓰지 않습니다.</span>
      </div>
      <div class="legend"><span><i class="swatch" style="background: var(--ink)" />주 1회 이상 사용 비율</span></div>
    </div>
    <ul class="adopt">
      <li v-for="t in adoption" :key="t.team">
        <span style="font-weight: 600">{{ t.team }}</span>
        <div class="bar" style="height: 10px"><div :class="{ low: t.rate < LOW }" :style="{ width: `${t.rate}%` }" /></div>
        <span class="num">{{ t.rate }}% · 이용권 {{ t.seats }}<template v-if="t.rate < LOW"> · 낮음</template></span>
      </li>
    </ul>
    <div v-if="lowTeams.length" class="inset hint">
      <span class="small" style="flex: 1 1 280px">{{ lowTeams.map((t) => t.team).join(', ') }} 팀 활용이 낮습니다. 등록 업무에 맞는 활용 제안을 다음 수집 때 우선 검토합니다.</span>
      <RouterLink to="/suggestions" class="btn btn-primary">자동 제안 기록 보기</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.adopt { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 14px; }
.adopt li { display: grid; grid-template-columns: minmax(110px, 160px) minmax(0, 1fr) 150px; align-items: center; gap: 16px; font-size: 14px; }
.adopt .num { text-align: right; }
.bar > div.low { background: var(--lime); outline: 1px solid rgba(17, 17, 19, 0.32); }
.hint { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 12px; padding: 16px; }
@media (max-width: 600px) {
  .adopt li { grid-template-columns: 1fr; gap: 6px; }
  .adopt .num { text-align: left; }
}
</style>
