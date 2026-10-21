<script setup>
import { ref, onMounted } from 'vue'
import { get } from '../api'
import { cap } from '../labels'
const rows = ref([])
onMounted(async () => { rows.value = await get('/unmet-needs') })
</script>
<template>
  <div class="page">
    <h2>미지원 요청</h2>
    <p class="hint">승인 제품으로 할 수 없었던 직원 요청입니다. 같은 기능이 3건 이상, 2개 부서 이상이면 새 제품 도입을 검토할 때입니다.</p>
    <el-table :data="rows" size="small">
      <el-table-column label="필요한 기능" width="160"><template #default="{ row }">{{ cap(row.capability_tag) }}</template></el-table-column>
      <el-table-column prop="count" label="요청 수" width="90" />
      <el-table-column prop="dept_count" label="요청한 부서 수" width="120" />
      <el-table-column label="도입 검토" width="100"><template #default="{ row }"><el-tag :type="row.threshold_met ? 'warning' : 'info'" size="small">{{ row.threshold_met ? '필요' : '아직' }}</el-tag></template></el-table-column>
      <el-table-column label="직원이 요청한 내용"><template #default="{ row }">{{ row.sample_summaries.join(' / ') }}</template></el-table-column>
    </el-table>
  </div>
</template>
