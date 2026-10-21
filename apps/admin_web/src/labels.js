// 화면 용어는 설계 문서 0절과 맞춘다.
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
