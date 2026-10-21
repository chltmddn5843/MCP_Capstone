// 시연용 가상 데이터 (A 코스메틱). 값은 apps/backend/fixtures.py 시드에 맞췄다.
// 실제 백엔드에 연결하면 이 파일은 지운다. 화면은 src/api.js만 본다.

export const me = { name: '광철', role: '관리자 · IT·자산관리' }

export const summary = {
  monthCost: 4180000, monthBudget: 4500000,
  seatsAssigned: 112, seatsTotal: 120, seatsToCheck: 7,
  savingsMonth: 270000, savingsNote: '아낀 구매 비용 6석 · 재배정',
  monthly: [
    { label: '5월', value: 3520000 }, { label: '6월', value: 3600000 }, { label: '7월', value: 3710000 },
    { label: '8월', value: 3800000 }, { label: '9월', value: 3950000 }, { label: '10월', value: 4180000 },
  ],
}

export const products = [
  {
    id: 'tool_ai_a', name: 'AI-A 채팅', plan: 'Enterprise', kind: 'AI', billing: '좌석 + 사용량 과금',
    seatsPurchased: 60, seatsAssigned: 60, seatPrice: 45000, monthCost: 2910000, renewal: '2026-12-31',
    seats: [
      { id: 'seat_01', name: '이도윤', dept: '해외영업', flag: 'on_leave', lastUsed: '72일 전', confirmation: '반납하겠다고 응답 · 10/20', action: 'plan' },
      { id: 'seat_02', name: '최하은', dept: 'SCM·물류', flag: 'unused', lastUsed: '64일 전', confirmation: '응답 대기 · 기한 10/24', action: 'remind' },
      { id: 'seat_03', name: '정민재', dept: '국내영업', flag: 'unused', lastUsed: '58일 전', confirmation: '계속 쓰겠다고 응답 · 유지', action: null },
      { id: 'seat_04', name: '한지아', dept: '연구개발', flag: 'no_record', lastUsed: '기록 없음', confirmation: '아직 묻지 않음', action: 'ask' },
      { id: 'seat_05', name: '오세린', dept: '마케팅', flag: 'recent_hire', lastUsed: '기록 없음', confirmation: '확인 필요 없음', action: null },
    ],
  },
  {
    id: 'tool_adobe', name: 'Adobe Acrobat', plan: 'Teams', kind: '일반 소프트웨어', billing: '정액 좌석제',
    seatsPurchased: 60, seatsAssigned: 52, seatPrice: 8000, monthCost: 420000, renewal: '2027-03-31',
    seats: [
      { id: 'seat_11', name: '강유나', dept: '재무·총무', flag: 'unused', lastUsed: '95일 전', confirmation: '응답 대기 · 기한 10/24', action: 'remind' },
      { id: 'seat_12', name: '서지호', dept: '상품기획', flag: 'no_record', lastUsed: '기록 없음', confirmation: '아직 묻지 않음', action: 'ask' },
    ],
  },
  {
    id: 'tool_ai_b', name: 'AI-B API', plan: 'Pay-as-you-go', kind: 'AI', billing: 'API 사용량 과금',
    seatsPurchased: 0, seatsAssigned: 0, seatPrice: 0, monthCost: 850000, renewal: '2026-12-31', projects: 3, seats: [],
  },
]

export const seatRequests = [
  { id: 'req_1', who: '박서준 · 마케팅', product: 'AI-A 채팅', purpose: '상세페이지 카피 작성', status: 'pending', note: '미배정 좌석 없음 → AI 의견과 함께 승인 대기로 이동' },
  { id: 'req_2', who: '김나래 · 국내영업', product: 'Adobe Acrobat', purpose: '계약서 PDF 편집', status: 'done', note: '미배정 좌석 배정 완료 · 10/21 09:12' },
  { id: 'req_3', who: '윤태오 · 상품기획', product: 'Adobe Acrobat', purpose: '문서 비교', status: 'done', note: '미배정 좌석 배정 완료 · 10/20 15:40' },
]

export const anomalies = [
  {
    id: 'anm_001', status: 'open', scopeName: '견적서 요약', product: 'AI-B API', model: 'B-large', env: '운영', dept: '국내영업',
    detectedAt: '오늘 08:30', baseline: 26000, observed: 81000, ratio: 3.1, projected: 1760000, budget: 800000, monthToDate: 612000,
    daily: [24000, 27000, 23000, 25000, 22000, 28000, 26000, 25000, 27000, 26000, 28000, 30000, 29000, 81000],
    dailyStart: '10/8',
    investigation: {
      doneAt: '08:31',
      causes: [
        { title: '요청당 입력 길이 증가', body: '평균 입력 1,900 → 7,400 토큰. 10/21부터 견적서 PDF 전체를 넣는 요청이 늘었습니다.' },
        { title: '같은 API 키의 반복 요청', body: 'key_sales_02에서 같은 문서 요청이 1시간에 40회 이상 반복됐습니다. 재시도 설정 문제일 수 있습니다.' },
      ],
      evidence: ['프로젝트 등록 목적·예산', '모델별 사용량', 'API 키별 요청 수', '입력 길이 분포'],
      actions: [
        { id: 'repeat_check', label: '반복 요청 점검 · 영업팀 확인 요청' },
        { id: 'budget_review', label: '예산 검토' },
        { id: 'model_review', label: '품질 평가 후 모델 검토' },
      ],
    },
  },
]

export const projects = [
  { id: 'prj_quote_summary', name: '견적서 요약', dept: '국내영업', model: 'B-large', env: '운영', cost: 612000, budget: 800000, anomaly: true },
  { id: 'prj_cs_classify', name: '고객 문의 분류', dept: 'CS', model: 'B-large', env: '운영', cost: 870000, budget: 1500000, anomaly: false },
  { id: 'prj_faq', name: '사내 FAQ', dept: '경영지원', model: 'B-mid', env: '테스트', cost: 94000, budget: 300000, anomaly: false },
]

// risk: low 바로 처리 · medium 담당자 승인 · high 책임자 결정
export const plans = [
  {
    id: 'PLN-0142', type: 'seat_reclaim', risk: 'medium', status: 'pending_approval', createdAt: '어제 16:20',
    title: '이용권 회수·재배정', subtitle: 'AI-A 채팅 · 이도윤 → 박서준', requester: '박서준 (마케팅)',
    summary: '휴직 중인 이도윤 님의 좌석을 회수해 박서준 님에게 배정합니다.',
    steps: [
      { label: '신청 접수', at: '10/20 14:02', done: true }, { label: 'AI 의견', at: '10/20 14:03', done: true },
      { label: '대상자 응답', at: '반납 동의 · 10/20', done: true }, { label: '관리자 승인', at: '지금 단계', current: true },
      { label: '실행·안내', at: '승인 후' },
    ],
    aiOpinion: { title: '재배정 권장', body: '미배정 좌석이 없습니다. 이도윤 님은 휴직 중이고 72일간 사용 기록이 없으며, 사용 의사 확인에 반납하겠다고 답했습니다. 재배정하면 추가 구매(월 45,000원)를 하지 않아도 됩니다. 복직 예정일(2027-01)에는 다시 신청이 필요할 수 있습니다.' },
    changes: [['회수', '이도윤 · 해외영업'], ['배정', '박서준 · 마케팅'], ['신청 목적', '상세페이지 카피 작성']],
    evidence: ['AI-A 계약 · 60석', '이도윤 사용 기록', '재직 상태 · 휴직', '사용 의사 응답 10/20'],
  },
  {
    id: 'PLN-0139', type: 'model_change', risk: 'medium', status: 'pending_approval', createdAt: '10/19',
    title: '테스트 환경 모델 변경', subtitle: '고객 문의 분류 · B-large → B-mid', requester: '최지민 (CS)',
    summary: '고객 문의 분류 프로젝트의 테스트 환경 모델을 B-mid로 바꿉니다. 운영 환경은 바꾸지 않습니다.',
    steps: [
      { label: '요청 접수', at: '10/19 11:10', done: true }, { label: '품질 평가 확인', at: '0.92 / 기준 0.90', done: true },
      { label: '관리자 승인', at: '지금 단계', current: true }, { label: '실행·안내', at: '승인 후' },
    ],
    aiOpinion: { title: '승인 가능', body: 'B-mid는 품질 0.92로 기준 0.90을 넘고 응답 시간이 900ms로 B-large(1,800ms)보다 빠릅니다. 같은 입력 길이 기준으로 월 예상 비용이 줄어듭니다.' },
    changes: [['프로젝트', '고객 문의 분류'], ['환경', '테스트'], ['모델', 'B-large → B-mid']],
    evidence: ['모델 품질 평가 ev_002', '승인 모델·단가', '프로젝트 사용량'],
  },
  {
    id: 'PLN-0137', type: 'purchase_review', risk: 'high', status: 'pending_approval', createdAt: '10/19',
    title: '추가 구매 검토', subtitle: 'AI-A 채팅 5석 · 결정만 기록, 구매는 시스템 밖', requester: '시스템',
    summary: '마케팅·상품기획에서 신청이 이어져 AI-A 채팅 5석 추가 구매를 검토합니다.',
    steps: [{ label: '요청 접수', at: '10/19', done: true }, { label: '책임자 결정', at: '지금 단계', current: true }],
    aiOpinion: { title: '재배정 후 재검토 권장', body: '확인 필요 좌석 5석 중 응답 대기 1석이 있습니다. 응답 기한(10/24) 뒤에 재배정 가능한 좌석을 먼저 확인하는 편이 좋습니다.' },
    changes: [['제품', 'AI-A 채팅'], ['수량', '5석'], ['월 비용', '+225,000원']],
    evidence: ['AI-A 계약 · 60석', '최근 30일 신청 4건', '확인 필요 좌석 5석'],
  },
]

export const updates = [
  {
    id: 'upd_1', product: 'AI-A 채팅', date: '10/20', title: '문서 비교 기능 출시 (Enterprise 플랜 포함)', result: 'sent', sourceUrl: '#',
    teams: [
      { team: '인사·HRD', result: 'sent', at: '10/21 10:00', reason: '등록 업무 "교육 과정별 설문 결과 비교"', reaction: '도움 됨 6 · 질문 1' },
      { team: '국내영업', result: 'sent', at: '10/21 10:00', reason: '등록 업무 "거래처 계약서 변경 조항 확인"', reaction: '도움 됨 4 · 관련 없음 1' },
      { team: '마케팅·디자인', result: 'held', reason: '이번 주 상한 2건 도달 → 다음 주로 미룸' },
      { team: 'SCM·물류', result: 'none', reason: '관련 등록 업무 없음' },
    ],
  },
  { id: 'upd_2', product: 'AI-A 채팅', date: '10/18', title: '음성 회의 실시간 번역', result: 'held', note: '전체 보류 · 회사 플랜(Enterprise)에 없는 기능', teams: [] },
  { id: 'upd_3', product: 'Adobe Acrobat', date: '10/16', title: 'PDF 양식 자동 채우기 개선', result: 'sent', note: '2개 팀에 보냄 · 해외영업, 재무·총무', teams: [] },
]

export const suggestionStats = { collected: 3, sent: 4, held: 5, helpfulRate: 71, nextRun: '10/27 월' }

export const teamSwitches = [
  { id: 'dept_hrd', team: '인사·HRD', channel: '#hrd', enabled: true },
  { id: 'dept_mkt', team: '마케팅·디자인', channel: '#mkt', enabled: true },
  { id: 'dept_sales', team: '국내영업', channel: '#sales', enabled: true },
  { id: 'dept_rnd', team: '연구개발', channel: '4주 보류 중', enabled: false },
]

export const unmetNeeds = [
  { capability: '이미지 생성', count: 7, depts: ['마케팅·디자인', '상품기획'], example: '광고 배너 시안 여러 개 만들기' },
  { capability: '번역', count: 4, depts: ['해외영업', '연구개발'], example: '바이어 메일 일본어 번역' },
  { capability: '회의록 요약', count: 3, depts: ['SCM·물류'], example: '주간 회의 녹음 요약' },
]

export const teamAdoption = [
  { team: '마케팅·디자인', rate: 82, seats: 18 }, { team: '상품기획·MD', rate: 74, seats: 12 },
  { team: '인사·HRD', rate: 70, seats: 5 }, { team: '국내영업', rate: 55, seats: 10 },
  { team: '해외영업', rate: 40, seats: 8 }, { team: 'SCM·물류', rate: 28, seats: 7 },
]
