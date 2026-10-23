<script setup>
// 활용 지원 › 미도입 제품 신청 (PRD S9). 직원이 "프리미어프로 신청해줘"처럼 사내 등록 제품에 없는 것을 말하면 AI 비서가 request_unlisted_product로
// 기록하고, 서버가 purchase_review 처리 요청을 '사내 미도입'으로 바로 반려해 이력에 남긴다. 여기서는 그 이력을 제품 이름으로 묶어 본다.
// 같은 제품 3건 이상 · 2개 부서 이상이면 '검토 기준 충족'. 그 제품은 [구매 검토 요청]으로 책임자 결정(승인 대기)에 올릴 수 있다 (실행은 시스템 밖).
import { ref, computed, onMounted } from 'vue'
import { getUnlistedRequests, createPurchaseReviewPlan } from '../api.js'
import { errorLabel } from '../request.js'
import { PLAN_STATUS } from '../labels.js'

const MET = { count: 3, depts: 2 } // 설계문서 D-2 기준
const rows = ref(null)
const selKey = ref('')
const busy = ref(false)
const notice = ref({ text: '', err: false, to: '' })
async function load() {
  rows.value = await getUnlistedRequests()
  if (!rows.value.some((r) => r.key === selKey.value)) selKey.value = rows.value[0]?.key ?? ''
}
onMounted(load)

const met = (r) => r.count >= MET.count && r.depts.length >= MET.depts
const sel = computed(() => rows.value?.find((r) => r.key === selKey.value))
const total = computed(() => ({
  requests: (rows.value ?? []).reduce((s, r) => s + r.count, 0), met: (rows.value ?? []).filter(met).length,
  depts: new Set((rows.value ?? []).flatMap((r) => r.depts)).size, reviewing: (rows.value ?? []).filter((r) => r.review && r.review.status === 'pending_approval').length,
}))
const dt = (s) => (s ? s.slice(5, 16).replace('T', ' ') : '')
const REVIEW = { pending_approval: { label: '구매 검토 · 책임자 결정 대기', tone: 'ok' }, approved: { label: '구매 검토 · 승인됨', tone: 'ok' }, executed: { label: '도입 결정', tone: 'ok' }, rejected: { label: '구매 검토 · 반려', tone: 'neutral' }, failed: { label: '구매 검토 · 실패', tone: 'neutral' } }
async function review(r) {
  if (busy.value) return
  busy.value = true; notice.value = { text: '', err: false, to: '' }
  try {
    const id = await createPurchaseReviewPlan(r)
    notice.value = { text: `${r.product} 구매 검토 요청을 만들었어요. 책임자 결정(승인 대기)으로 올라갔고, 결정은 기록만 남기고 구매는 시스템 밖에서 진행합니다.`, err: false, to: `/inbox?id=${id}` }
    await load()
  } catch (e) { notice.value = { text: errorLabel(e), err: true, to: '' } }
  busy.value = false
}
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">활용 지원 · 직원이 신청했지만 사내 등록 제품에 없는 것</span><h1>미도입 제품 신청</h1></div>
  </header>

  <p v-if="!rows" class="card small muted loading" aria-busy="true">신청 이력을 불러오는 중…</p>
  <template v-else>
    <section class="kpis" aria-label="미도입 제품 신청 요약">
      <div class="card-dark kpi"><span class="small muted">신청 누적</span><span class="value">{{ total.requests }}건</span><span class="xs muted">제품 {{ rows.length }}가지 · 부서 {{ total.depts }}곳</span></div>
      <div class="kpi" :class="total.met ? 'card-lime' : 'card'"><span class="small" :class="{ muted: !total.met }">검토 기준 충족</span><span class="value">{{ total.met }}건</span><span class="xs" :class="{ muted: !total.met }">같은 제품 {{ MET.count }}건 이상 · {{ MET.depts }}개 부서 이상</span></div>
      <RouterLink to="/inbox" class="card kpi"><span class="small muted">구매 검토 올린 것</span><span class="value">{{ total.reviewing }}건</span><span class="xs muted">책임자 결정 대기 · 승인 대기에서 보기</span></RouterLink>
    </section>

    <div class="row">
      <section class="card col-3" aria-labelledby="need-h">
        <div class="card-head">
          <div><h2 id="need-h">신청된 제품</h2><span class="small muted">AI 비서가 "사내 미도입"으로 안내하고 남긴 이력 · 많이 신청된 제품부터</span></div>
        </div>
        <p v-if="notice.text" class="status xs" :class="{ err: notice.err }" :role="notice.err ? 'alert' : 'status'" style="margin: 0">{{ notice.text }} <RouterLink v-if="notice.to" :to="notice.to" style="font-weight: 700; margin-left: 6px">승인 대기 보기</RouterLink></p>
        <div v-if="rows.length" class="table-wrap">
          <table class="table" style="min-width: 680px">
            <thead><tr><th scope="col">제품</th><th scope="col" class="num">신청</th><th scope="col">신청 부서</th><th scope="col">최근 신청</th><th scope="col">상태</th></tr></thead>
            <tbody>
              <tr v-for="r in rows" :key="r.key" :class="{ picked: r.key === selKey }">
                <th scope="row"><button type="button" class="feat" :aria-pressed="r.key === selKey" @click="selKey = r.key">{{ r.product }}</button></th>
                <td class="num">{{ r.count }}건</td>
                <td><span v-for="d in r.depts" :key="d" class="chip chip-sm">{{ d }}</span><span v-if="!r.depts.length" class="muted">-</span></td>
                <td class="small muted">{{ r.lastLabel || '-' }}</td>
                <td>
                  <span v-if="r.review && REVIEW[r.review.status]" class="pill" :class="`pill-${REVIEW[r.review.status].tone}`">{{ REVIEW[r.review.status].label }}</span>
                  <span v-else class="pill" :class="met(r) ? 'pill-alert' : 'pill-neutral'">{{ met(r) ? '검토 기준 충족' : `${r.count}/${MET.count}건 · ${r.depts.length}/${MET.depts}부서` }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="inset" style="gap: 6px">
          <strong>아직 신청 이력이 없습니다</strong>
          <span class="small muted">직원이 Slack이나 AI 비서에서 사내 등록 제품에 없는 제품을 신청하면 여기에 쌓입니다. 예: "프리미어프로 신청해줘"</span>
        </div>
      </section>

      <aside v-if="sel" class="card col-1 detail" aria-labelledby="sel-h">
        <h2 id="sel-h">{{ sel.product }}</h2>
        <span class="pill" :class="met(sel) ? 'pill-alert' : 'pill-neutral'" style="align-self: flex-start">{{ met(sel) ? '검토 기준 충족' : '아직 기준 미달' }}</span>
        <dl class="facts">
          <div><dt class="xs muted">신청</dt><dd>{{ sel.count }}건 · {{ sel.depts.join(', ') || '부서 미상' }}</dd></div>
          <div v-if="sel.purposes.length"><dt class="xs muted">직원이 말한 용도</dt><dd class="small">{{ [...new Set(sel.purposes)].slice(0, 3).join(' / ') }}</dd></div>
          <div><dt class="xs muted">신청한 직원</dt><dd class="small">{{ sel.requesters.map((q) => `${q.name}${q.dept ? ` (${q.dept})` : ''} · ${dt(q.at)}`).join('\n') }}</dd></div>
        </dl>
        <template v-if="sel.review && REVIEW[sel.review.status]">
          <span class="pill" :class="`pill-${REVIEW[sel.review.status].tone}`" style="align-self: flex-start">{{ REVIEW[sel.review.status].label }} · {{ dt(sel.review.at) }}</span>
          <RouterLink :to="{ path: '/inbox', query: { id: sel.review.id } }" class="btn btn-sm">{{ PLAN_STATUS[sel.review.status] ?? sel.review.status }} · 승인 대기에서 보기</RouterLink>
        </template>
        <template v-else>
          <h3 class="small">할 일</h3>
          <button type="button" class="btn btn-sm" :class="{ 'btn-dark': met(sel) }" :disabled="busy" @click="review(sel)">{{ busy ? '만드는 중…' : '구매 검토 요청 만들기' }}</button>
          <span class="xs muted">{{ met(sel) ? '기준을 충족했어요. ' : '기준 미달이어도 올릴 수 있어요. ' }}책임자 결정(승인 대기)으로 가고, 결정은 기록만 남깁니다. 구매·계약은 시스템 밖에서 합니다.</span>
        </template>
        <span class="xs muted">신청한 직원에게는 이미 "현재 사내 제공 대상이 아니므로 반려되었습니다"라고 안내됐습니다. 도입이 결정되면 회사 설정 › 구독 제품에 등록한 뒤 다시 신청하게 하세요.</span>
      </aside>
    </div>
  </template>
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
.facts dd { margin: 0; white-space: pre-line; }
.btn { align-self: flex-start; }
@media (max-width: 900px) { .detail { position: static; } }
</style>
