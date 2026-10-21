// 화면 용어 (docs/설계문서.md 0절). apps/admin_ui/labels.py와 같은 값을 유지한다.
export const ROLE = { employee: '직원', admin: '관리자', system: '시스템' }
export const PLAN_TYPE = { seat_assign: '이용권 배정', seat_reclaim: '이용권 회수·재배정', model_change: '모델 변경', budget_review: '예산 검토', purchase_review: '구매 검토' }
export const PLAN_STATUS = { draft: '작성 중', pending_approval: '승인 대기', approved: '승인됨 · 처리 전', executed: '처리 완료', failed: '처리 실패', rejected: '반려' }
export const RISK = { low: '바로 처리', medium: '담당자 승인', high: '책임자 결정 · 요청만 기록' }
export const FLAG = { unused: '장기 미사용', on_leave: '휴직 중', no_record: '사용 기록 없음 → 본인 확인 필요', recent_hire: '최근 입사 (정상)' }
export const BILLING = { seat_flat: '정액 좌석제', seat_plus_usage: '좌석 + 사용량 과금', api_usage: 'API 사용량 과금' }
export const TASK_STATUS = { queued: '대기', running: '처리 중', waiting_approval: '관리자 확인 대기', done: '완료', failed: '실패' }
export const SUGGESTION_STATUS = { draft: '작성됨', pending_approval: '발송 대기', sent: '보냄', on_hold: '보내지 않음' }
export const ANOMALY_STATUS = { open: '확인 전', investigating: '조사 중', resolved: '처리 완료' }
export const SAVINGS = { purchase_avoided: '아낀 구매 비용', renewal_reduced: '갱신 때 줄인 비용', billing_reduced: '줄어든 청구액', projected: '예상 절감' }
export const TOOL = {
  get_my_profile: '내 정보와 등록 업무 확인', upsert_my_task: '업무 등록', list_approved_tools: '승인 제품·플랜 확인', list_approved_models: '승인 모델·단가 확인',
  find_relevant_tasks: '관련 팀·업무 찾기', save_suggestion: '활용 제안 저장', get_team_adoption: '팀별 활용 현황 조회', get_eval_results: '모델 품질 평가 조회',
  estimate_task_cost: '예상 비용 계산', get_usage_summary: '사용량 조회', get_usage_breakdown: '사용량 세부 분석', get_anomalies: '비용 급증 알림 조회',
  get_anomaly_detail: '알림 상세와 프로젝트 정보 확인', get_license_inventory: '이용권 현황 조회', record_unmet_need: '미지원 요청 기록', list_unmet_needs: '미지원 요청 집계',
  request_confirmation: '사용 의사 확인 요청', create_action_plan: '처리 요청 작성', get_plan_status: '처리 요청 상태 확인', execute_approved_plan: '승인된 요청 처리',
  search_vendor_docs: '제품 공식 문서 검색', get_vendor_update: '업데이트 내용 확인', search_internal_policy: '사내 정책 검색',
}
export const CAPABILITY = { contract_compare: '계약서 비교', doc_compare: '문서 비교', image_gen: '이미지 생성', meeting_summary: '회의록 요약', code_review: '코드 리뷰', translation: '번역', data_extraction: '문서에서 데이터 추출', pdf_edit: 'PDF 편집' }
export const ERROR_CODE = { unauthorized: '로그인이 필요합니다', forbidden: '권한이 없습니다', not_found: '찾을 수 없습니다', invalid: '입력이 올바르지 않습니다', conflict: '현재 상태에서는 할 수 없습니다', stale: '승인 뒤 상황이 바뀌어 처리를 멈췄습니다', rejected: '관리자가 거절했습니다', agent_unavailable: 'AI 비서 서버가 응답하지 않습니다' }
export const QUICK = {
  employee: ['AI-A 이용권 신청하고 싶어요', '고객 문의 1,000건을 매일 10개 유형으로 분류하는데 비용을 줄일 수 있을까요?', '문서 비교 기능을 회사 플랜에서 써도 되나요?', '내 등록 업무 알려줘'],
  admin: ['견적서 요약 프로젝트 비용이 왜 늘었는지 조사해줘', '안 쓰는 것으로 보이는 이용권을 검토해서 처리 요청을 제안해줘', '박서준 님 AI-A 이용권 배정해줘', '이번 달 절감 기록 요약해줘'],
}
export const cap = t => CAPABILITY[t] || (t || '').replaceAll('_', ' ')
export const won = n => (n == null ? '-' : `${Math.round(n).toLocaleString('ko-KR')}원`)
export const dt = s => (s ? s.slice(0, 16).replace('T', ' ') : '-')
