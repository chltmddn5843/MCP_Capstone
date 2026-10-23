<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getProducts, getSeatRequests, requestConfirmation } from '../api.js'
import { FLAG, won, pct, onTabKeys } from '../labels.js'
import ProductLogo from '../components/ProductLogo.vue'

const products = ref([])
const requests = ref([])
const activeId = ref('')
const flagFilter = ref('all')
const notice = ref({ text: '', err: false })
const loaded = ref(false)
const asking = ref('') // 확인 요청 보내는 중인 직원 id (중복 클릭 방지)

async function load() {
  ;[products.value, requests.value] = await Promise.all([getProducts(), getSeatRequests()])
  activeId.value ||= products.value[0]?.id
  loaded.value = true
}
onMounted(() => {
  load()
  const onFocus = () => { if (document.visibilityState === 'visible') load() }  // 승인·실행 뒤 돌아오면 다시 읽는다
  window.addEventListener('focus', onFocus); document.addEventListener('visibilitychange', onFocus)
  onBeforeUnmount(() => { window.removeEventListener('focus', onFocus); document.removeEventListener('visibilitychange', onFocus) })
})

const product = computed(() => products.value.find((p) => p.id === activeId.value))
const flagged = computed(() => product.value?.seats ?? [])
const toCheck = computed(() => flagged.value.filter((s) => s.flag !== 'recent_hire').length)
const visible = computed(() => flagged.value.filter((s) => flagFilter.value === 'all' || s.flag === flagFilter.value))
const filters = computed(() => [
  { id: 'all', label: '전체', n: flagged.value.length },
  ...Object.keys(FLAG).map((id) => ({ id, label: FLAG[id].label, n: flagged.value.filter((s) => s.flag === id).length })).filter((f) => f.n),
])

function selectProduct(id) { activeId.value = id; flagFilter.value = 'all' }
async function ask(seat) {
  asking.value = seat.id
  try { await requestConfirmation(seat.id); notice.value = { text: `${seat.name} 님에게 사용 의사 확인을 보냈습니다.`, err: false } }
  catch (e) { notice.value = { text: `확인 요청 실패: ${e.message}`, err: true } }
  finally { asking.value = '' }
  await load()
}
</script>

<template>
  <header class="page-head">
    <div><span class="small muted">운영 · 좌석 배정과 사용 의사 확인</span><h1>구독·이용권</h1></div>
  </header>

  <div role="tablist" aria-label="제품" class="tags" style="gap: 8px" @keydown="onTabKeys">
    <button v-for="p in products" :key="p.id" type="button" role="tab" class="chip chip-lg prod-tab" :aria-selected="p.id === activeId" :tabindex="p.id === activeId ? 0 : -1" @click="selectProduct(p.id)">
      <ProductLogo :tool-id="p.id" :name="p.name" :size="24" />{{ p.name }} · {{ p.seatsPurchased ? `${p.seatsPurchased}석` : '좌석 없음' }}
    </button>
  </div>

  <template v-if="product">
    <section class="card" :aria-label="`${product.name} 이용권 요약`">
      <div class="facts">
        <div><span class="small muted">과금 방식</span><strong>{{ product.billing }}</strong></div>
        <template v-if="product.seatsPurchased">
          <div><span class="small muted">계약</span><strong>{{ product.seatsPurchased }}석</strong></div>
          <div><span class="small muted">배정</span><strong>{{ product.seatsAssigned }}석</strong></div>
          <div><span class="small muted">미배정</span><strong>{{ product.seatsPurchased - product.seatsAssigned }}석</strong></div>
          <div><span class="small muted">본인 확인 필요</span><strong>{{ toCheck }}석</strong></div>
          <div><span class="small muted">좌석 단가</span><strong>{{ won(product.seatPrice) }}</strong></div>
        </template>
        <div v-else><span class="small muted">쓰는 프로젝트</span><strong>{{ product.projects }}개</strong></div>
      </div>
      <template v-if="product.seatsPurchased">
        <div class="stackbar" role="img" :aria-label="`${product.seatsPurchased}석 중 사용 중 ${product.seatsAssigned - toCheck}석, 본인 확인 필요 ${toCheck}석, 미배정 ${product.seatsPurchased - product.seatsAssigned}석`">
          <div class="seg-ink" :style="{ width: `${pct(product.seatsAssigned - toCheck, product.seatsPurchased)}%` }" />
          <div class="seg-lime" :style="{ width: `${pct(toCheck, product.seatsPurchased)}%` }" />
        </div>
        <div class="legend">
          <span><i class="swatch" style="background: var(--ink)" />사용 중 {{ product.seatsAssigned - toCheck }}</span>
          <span><i class="swatch" style="background: var(--lime); outline: 1px solid rgba(17,17,19,.24)" />본인 확인 필요 {{ toCheck }}</span>
          <span><i class="swatch" style="background: var(--track)" />미배정 {{ product.seatsPurchased - product.seatsAssigned }}</span>
        </div>
      </template>
      <p v-else class="small muted" style="margin: 0">API 사용량 과금 제품은 좌석이 없습니다. 좌석별 오늘 토큰 소비는 <RouterLink to="/cost/teams">팀별 사용량·좌석 배치도</RouterLink>에서 봅니다.</p>
    </section>

    <div class="row">
      <section class="card col-3" aria-labelledby="seat-h">
        <div class="card-head">
          <div>
            <h2 id="seat-h">확인이 필요한 이용권</h2>
            <span class="small muted">사용 기록이 없다는 이유만으로 회수하지 않습니다. 먼저 본인에게 사용 의사를 묻습니다.</span>
          </div>
          <div v-if="flagged.length" class="tags">
            <button v-for="f in filters" :key="f.id" type="button" class="chip" :aria-pressed="flagFilter === f.id" @click="flagFilter = f.id">{{ f.label }} {{ f.n }}</button>
          </div>
        </div>
        <p v-if="notice.text" class="status" :class="{ err: notice.err }" :role="notice.err ? 'alert' : 'status'">{{ notice.text }}</p>
        <div v-if="visible.length" class="table-wrap">
          <table class="table" style="min-width: 680px">
            <thead><tr><th scope="col">직원</th><th scope="col">상태</th><th scope="col">마지막 사용</th><th scope="col">사용 의사 확인</th><th scope="col" class="num"><span class="sr-only">동작</span></th></tr></thead>
            <tbody>
              <tr v-for="seat in visible" :key="seat.id">
                <td><div class="cell-2"><span>{{ seat.name }}</span><span>{{ seat.dept }}</span></div></td>
                <td><span class="pill" :class="`pill-${FLAG[seat.flag].tone}`">{{ FLAG[seat.flag].label }}</span></td>
                <td :class="{ muted: seat.lastUsed === '기록 없음' }">{{ seat.lastUsed }}</td>
                <td>{{ seat.confirmation }}</td>
                <td class="num">
                  <button v-if="seat.action === 'ask'" type="button" class="btn btn-dark btn-sm" :disabled="!!asking" @click="ask(seat)">{{ asking === seat.id ? '보내는 중…' : '본인 확인 요청' }}</button>
                  <span v-else class="small muted">처리 없음</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="small muted">확인이 필요한 이용권이 없습니다.</p>
      </section>

      <aside class="col-1 stack">
        <section class="card" aria-labelledby="req-h">
          <div class="card-head"><h2 id="req-h">이용권 신청</h2><span class="small muted">최근 {{ requests.length }}건</span></div>
          <div v-for="r in requests" :key="r.id" class="inset" :class="{ outline: r.status === 'done' }">
            <div class="req-top">
              <strong class="small">{{ r.who }}</strong>
              <span class="pill" :class="r.status === 'pending' ? 'pill-ok' : 'pill-neutral'">{{ r.status === 'pending' ? '승인 대기' : '처리 완료' }}</span>
            </div>
            <span class="small muted">{{ r.product }} · {{ r.purpose }}</span>
            <span class="small">{{ r.note }}</span>
            <RouterLink v-if="r.status === 'pending'" to="/inbox" class="small strong">승인 대기에서 보기</RouterLink>
          </div>
        </section>
        <section class="card-dark small" aria-label="처리 규칙" style="line-height: 1.6">
          <strong style="color: var(--lime)">처리 규칙</strong>
          <span>신청은 AI 의견과 함께 승인 대기로 오고, 승인하면 미배정 좌석에서 배정합니다.</span>
          <span>좌석이 없으면 승인할 수 없고 반려합니다. 추가 구매는 하지 않습니다.</span>
          <span>재배정은 대상자의 사용 의사 응답이 있어야 실행됩니다.</span>
        </section>
      </aside>
    </div>
  </template>
  <p v-else-if="loaded" class="card small muted loading">아직 등록한 구독 제품이 없습니다. <RouterLink to="/setup?step=assets">회사 설정에서 제품 등록하기</RouterLink></p>
  <p v-else class="card small muted loading" aria-busy="true">이용권 현황을 불러오는 중…</p>
</template>

<style scoped>
.prod-tab { display: inline-flex; align-items: center; gap: 8px; padding-left: 8px; }
.facts { display: flex; flex-wrap: wrap; gap: 32px; }
.facts div { display: flex; flex-direction: column; gap: 4px; }
.facts strong { font-size: 24px; }
.stackbar { display: flex; height: 12px; border-radius: 999px; overflow: hidden; background: rgba(17, 17, 19, 0.08); }
.seg-ink { background: var(--ink); }
.seg-lime { background: var(--lime); }
.strong { font-weight: 700; }
.inset.outline { background: transparent; border: 1px solid var(--line); }
.req-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
</style>
