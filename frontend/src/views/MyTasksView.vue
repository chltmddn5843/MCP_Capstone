<script setup>
import { ref, onMounted } from 'vue'
import { get } from '../api'
import { BILLING, PLAN_TYPE, PLAN_STATUS, dt } from '../labels'
const me = ref(null), plans = ref([])
onMounted(async () => { me.value = await get('/me'); plans.value = (await get('/plans')).items })
</script>
<template>
  <div class="page" v-if="me">
    <h2>내 업무와 이용권</h2>
    <h3>등록한 업무</h3>
    <p class="hint">여기 등록된 업무를 기준으로 새 기능 제안과 모델 추천이 맞춰집니다. AI 비서에게 말하면 등록·수정할 수 있습니다.</p>
    <el-table :data="me.tasks" size="small" class="card">
      <el-table-column prop="title" label="업무" width="220" /><el-table-column prop="description" label="설명" /><el-table-column prop="frequency" label="주기" width="90" />
      <el-table-column label="사용 제품" width="160"><template #default="{ row }">{{ row.tools_used.join(', ') }}</template></el-table-column>
    </el-table>
    <h3>내가 쓸 수 있는 제품</h3>
    <el-table :data="me.available_tools" size="small" class="card">
      <el-table-column prop="product" label="제품" width="200" /><el-table-column prop="vendor" label="제공사" width="100" />
      <el-table-column label="플랜" width="200"><template #default="{ row }">{{ row.contract?.plan_name || '-' }}</template></el-table-column>
      <el-table-column label="과금" width="140"><template #default="{ row }">{{ BILLING[row.contract?.billing_type] || '-' }}</template></el-table-column>
      <el-table-column prop="policy_note" label="유의사항" />
    </el-table>
    <h3>내 신청 현황</h3>
    <el-table :data="plans" size="small">
      <el-table-column label="신청" width="160"><template #default="{ row }">{{ PLAN_TYPE[row.type] || row.type }}</template></el-table-column>
      <el-table-column label="상태" width="140"><template #default="{ row }">{{ PLAN_STATUS[row.status] || row.status }}</template></el-table-column>
      <el-table-column prop="rationale" label="내용" />
      <el-table-column label="신청일" width="150"><template #default="{ row }">{{ dt(row.created_at) }}</template></el-table-column>
    </el-table>
  </div>
</template>
