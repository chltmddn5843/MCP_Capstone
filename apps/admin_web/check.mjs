// node check.mjs — api.js 목업 상태 전이 확인 (승인 대기 배지, 처리 요청 생성·승인·반려)
import assert from 'node:assert/strict'
import * as api from './src/api.js'

assert.deepEqual(await api.getCounts(), { inbox: 3, cost: 1 })

const id = await api.createPlanFromAnomaly('anm_001', 'budget_review')
assert.deepEqual(await api.getCounts(), { inbox: 4, cost: 0 }, '알림 대응 요청은 승인 대기로 가고 알림은 조사 중이 된다')

assert.equal(await api.approvePlan(id), 'executed')
assert.equal(await api.approvePlan('PLN-0137'), 'approved', '책임자 결정은 기록만 하고 실행하지 않는다')
await api.rejectPlan('PLN-0139')
assert.equal((await api.getCounts()).inbox, 1)

const plans = await api.getPlans()
plans[0].status = 'x'
assert.notEqual((await api.getPlans())[0].status, 'x', '화면이 받은 값을 고쳐도 원본은 바뀌지 않는다')

console.log('ok')
