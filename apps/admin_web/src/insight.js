// 좌석·팀 경보의 '왜'와 '어떻게'를 숫자에서 문장으로 만든다. LLM 없이 화면에서 바로 나온다 (GET /usage/seats/{id}의 분포 + 이용권 상태).
// AI 분석(analyze_seat_usage)은 이 위에 버튼으로 더한다. 사용량은 이용권 관리에만 쓰고 인사평가에 쓰지 않는다.
import { FLAG } from './labels.js'

const LIGHT = /mini|haiku|flash|nano|lite|small/i // 이름으로 보는 '가벼운 모델'. 단가 비교는 models 목록이 있을 때만
const LONG = 0.4 // 8k+ 입력 비중이 이 이상이면 '긴 입력'
const HEAVY = 0.5 // 한 모델 비중이 이 이상이면 '무거운 모델'
const BURST = 0.5 // 한 시간대 비중이 이 이상이면 '특정 시간 집중'
const pc = (x) => Math.round(x * 100)
const top = (rows = []) => rows.slice().sort((a, b) => b.share - a.share)[0]
const STATUS = { on_leave: '휴직 중', resigned: '퇴사' }

/** 같은 공급사의 더 가벼운 승인 모델 (없으면 null). models = GET /models.
 *  API 모델은 바로 아래 단가, 좌석 제품(ChatGPT 등)은 단가가 0이라 이름(mini·haiku…)으로 고른다 */
export function lighterModel(name, models = []) {
  const m = models.find((x) => x.name === name)
  if (!m) return null
  const same = models.filter((x) => x.vendor === m.vendor && x.name !== m.name)
  const cheaper = same.filter((x) => x.input_usd_per_mtok < m.input_usd_per_mtok).sort((a, b) => b.input_usd_per_mtok - a.input_usd_per_mtok)[0]
  return cheaper ?? same.find((x) => LIGHT.test(x.name)) ?? null
}

/**
 * 한 자리의 이유·해결책. 반환: { reasons: [{ key, title, body }], fixes: [string] }
 * pace·detail은 토큰 좌석일 때만, tools·status는 이용권 확인(장기 미사용·휴직 등)용.
 */
export function seatInsight({ pace, detail, tools = [], status = 'active', models = [] } = {}) {
  const reasons = [], fixes = []
  if (pace && pace.level !== 'normal') {
    const d = detail ?? { by_input_length: [], by_model: [], by_hour: [] }
    const long = d.by_input_length.filter((b) => b.key === '8k+').reduce((s, b) => s + b.share, 0)
    if (long >= LONG) {
      reasons.push({ key: 'long', title: '긴 입력', body: `오늘 토큰의 ${pc(long)}%가 8천 토큰이 넘는 긴 입력이에요. 문서를 통째로 넣는 작업으로 보여요.` })
      fixes.push('긴 문서는 필요한 부분만 잘라서 넣기')
    }
    const tm = top(d.by_model)
    if (tm && tm.share >= HEAVY && !LIGHT.test(tm.key)) {
      const lighter = lighterModel(tm.key, models)
      const m = models.find((x) => x.name === tm.key)
      reasons.push({ key: 'heavy', title: '무거운 모델', body: `${tm.key} 모델이 ${pc(tm.share)}%예요. 초안·요약처럼 가벼운 작업도 큰 모델로 돌리고 있을 수 있어요.` })
      const cheaper = lighter && m.input_usd_per_mtok > 0 && lighter.input_usd_per_mtok < m.input_usd_per_mtok ? ` (입력 단가 ${pc(1 - lighter.input_usd_per_mtok / m.input_usd_per_mtok)}% 저렴)` : ''
      fixes.push(lighter ? `초안·요약 같은 작업은 ${lighter.name}${cheaper}로 바꾸기` : '초안·요약 같은 작업은 같은 좌석의 가벼운 모델로 바꾸기')
    }
    const th = top(d.by_hour)
    if (th && d.by_hour.length > 1 && th.share >= BURST) {
      reasons.push({ key: 'burst', title: '특정 시간 집중', body: `${th.key}시에 ${pc(th.share)}%가 몰려 있어요. 한 번에 몰아서 돌리는 작업일 수 있어요.` })
      fixes.push('일시적인 작업이면 내일 다시 확인')
    }
    if (pace.projected_quota_pct >= 100) {
      reasons.push({ key: 'quota', title: '하루 한도 초과 예상', body: `이 속도면 오늘 하루 한도의 ${Math.round(pace.projected_quota_pct)}%를 쓰게 돼요.` })
      fixes.push('한도를 넘기면 작업이 끊기니 본인에게 미리 알리기')
    }
    if (!reasons.length) {
      reasons.push({ key: 'general', title: '전반적으로 많이 사용', body: `특정 패턴 없이 같은 제품 좌석 평균의 ${pace.ratio}배 속도예요.` })
      fixes.push('본인에게 진행 중인 작업 확인 (경보 DM이 이미 갔어요)')
    }
  }
  if (STATUS[status]) {
    reasons.push({ key: `status_${status}`, title: STATUS[status], body: `${STATUS[status]}인데 이용권이 그대로 배정돼 있어요.` })
    fixes.push(status === 'resigned' ? '이용권 회수 (구독·이용권에서 처리 요청)' : '휴직 기간 동안 이용권 회수 검토')
  }
  for (const t of tools) {
    if (!t.flag || t.flag === 'recent_hire' || t.flag === 'on_leave') continue
    if (t.flag === 'unused') { reasons.push({ key: 'unused', title: `${t.product} 장기 미사용`, body: '30일 넘게 사용 기록이 없어요. 자리만 차지하는 이용권일 수 있어요.' }); fixes.push('구독·이용권에서 사용 의사 확인 요청 보내기 (답이 없으면 회수 후보)') }
    else if (t.flag === 'no_record') { reasons.push({ key: 'no_record', title: `${t.product} 사용 기록 없음`, body: '공급사가 사용 기록을 주지 않는 제품이라 마지막 사용일로만 판단해요.' }); fixes.push('본인에게 사용 여부를 물어보기') }
    else reasons.push({ key: t.flag, title: FLAG[t.flag]?.label ?? t.flag, body: `${t.product} 이용권 상태를 확인해 주세요.` })
  }
  return { reasons, fixes: [...new Set(fixes)] }
}

/**
 * 팀(구역)에 붙는 배지 하나. 우선순위: 2배 이상 좌석 > API 예산 초과 > 빠름 좌석 > 이용권 확인. rank가 클수록 위에 정렬.
 */
export function teamBadge({ over = 0, caution = 0, checks = 0, apiOver = false } = {}) {
  if (over) return { label: `2배 이상 ${over}석`, tone: 'alert', rank: 4 }
  if (apiOver) return { label: '확인 필요 · API 예산 초과', tone: 'alert', rank: 3 }
  if (caution) return { label: `확인 필요 · 빠름 ${caution}석`, tone: 'ok', rank: 2 }
  if (checks) return { label: `확인 필요 · 이용권 ${checks}명`, tone: 'neutral', rank: 1 }
  return null
}

/** 경보 좌석 여러 개의 insight에서 과반(2개 이상)에 겹치는 이유만 '팀 패턴'으로 뽑는다 */
export function teamPattern(insights) {
  const n = insights.length
  if (n < 2) return { common: [], fixes: [] }
  const count = new Map(), fixes = new Map()
  for (const ins of insights) {
    for (const r of ins.reasons) { const c = count.get(r.key) ?? { ...r, n: 0 }; c.n += 1; count.set(r.key, c) }
    for (const f of ins.fixes) fixes.set(f, (fixes.get(f) ?? 0) + 1)
  }
  const common = [...count.values()].filter((c) => c.n >= Math.max(2, Math.ceil(n / 2))).sort((a, b) => b.n - a.n)
  const keys = new Set(common.map((c) => c.key))
  const fix = [...fixes.entries()].filter(([, c]) => c >= Math.max(2, Math.ceil(n / 2))).map(([f]) => f)
  return { common: common.map((c) => ({ ...c, body: `${c.n}명이 같은 패턴 · ${c.body}` })), fixes: keys.size ? fix.slice(0, 3) : [] }
}
