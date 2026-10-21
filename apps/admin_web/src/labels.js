// 화면 용어. apps/admin_ui/labels.py와 같은 말을 쓴다 (설계 문서 0절).
// tone: alert(다크 배지) · ok(라임 배지) · neutral(외곽선 배지)
export const FLAG = {
  unused: { label: '장기 미사용', tone: 'alert' },
  on_leave: { label: '휴직 중', tone: 'alert' },
  no_record: { label: '사용 기록 없음', tone: 'neutral' },
  recent_hire: { label: '최근 입사 · 정상', tone: 'ok' },
}
export const RISK = {
  low: { label: '바로 처리', tone: 'neutral' },
  medium: { label: '담당자 승인', tone: 'ok' },
  high: { label: '책임자 결정', tone: 'alert' },
}
export const PLAN_STATUS = {
  pending_approval: '승인 대기', approved: '승인됨 · 처리 전', executed: '처리 완료', failed: '처리 실패', rejected: '반려',
}
export const SEND_RESULT = {
  sent: { label: '보냄', tone: 'ok' },
  held: { label: '보내지 않음', tone: 'alert' },
  none: { label: '해당 없음', tone: 'neutral' },
}

export const won = (n) => (n == null ? '-' : `${Math.round(n).toLocaleString('ko-KR')}원`)
export const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0)

// 아래는 백엔드 값 → 화면 말 변환용 (api.js, AI 비서 스트림)
export const PLAN_TYPE = { seat_assign: '이용권 배정', seat_reclaim: '이용권 회수·재배정', model_change: '모델 변경', budget_review: '예산 검토', purchase_review: '구매 검토' }
export const BILLING = { seat_flat: '정액 좌석제', seat_plus_usage: '좌석 + 사용량 과금', api_usage: 'API 사용량 과금' }
export const TASK_STATUS = { queued: '대기', running: '처리 중', waiting_approval: '관리자 확인 대기', done: '완료', failed: '실패' }
export const TOOL_LABEL = {
  get_my_profile: '내 정보와 등록 업무 확인', upsert_my_task: '업무 등록', list_approved_tools: '승인 제품·플랜 확인', list_approved_models: '승인 모델·단가 확인',
  find_relevant_tasks: '관련 팀·업무 찾기', save_suggestion: '활용 제안 저장', get_team_adoption: '팀별 활용 현황 조회', get_eval_results: '모델 품질 평가 조회',
  estimate_task_cost: '예상 비용 계산', get_usage_summary: '사용량 조회', get_usage_breakdown: '사용량 세부 분석', get_anomalies: '비용 급증 알림 조회',
  get_anomaly_detail: '알림 상세와 프로젝트 정보 확인', get_license_inventory: '이용권 현황 조회', record_unmet_need: '미지원 요청 기록', list_unmet_needs: '미지원 요청 집계',
  request_confirmation: '사용 의사 확인 요청', create_action_plan: '처리 요청 작성', get_plan_status: '처리 요청 상태 확인', execute_approved_plan: '승인된 요청 처리',
  search_vendor_docs: '제품 공식 문서 검색', get_vendor_update: '업데이트 내용 확인', search_internal_policy: '사내 정책 검색',
}
export const CAPABILITY = { contract_compare: '계약서 비교', doc_compare: '문서 비교', image_gen: '이미지 생성', meeting_summary: '회의록 요약', code_review: '코드 리뷰', translation: '번역', data_extraction: '문서에서 데이터 추출', pdf_edit: 'PDF 편집' }
export const cap = (t) => CAPABILITY[t] ?? (t ?? '').replaceAll('_', ' ')
export const QUICK = ['견적서 요약 프로젝트 비용이 왜 늘었는지 조사해줘', '안 쓰는 것으로 보이는 이용권을 검토해서 처리 요청을 제안해줘', '박서준 님 AI-A 이용권 배정해줘', '이번 달 절감 기록 요약해줘']
