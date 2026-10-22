"""기능 사용 설명서(구글 시트 '화면 가이드' 탭)용 화면 캡처. 실제 화면에 번호 박스를 그려 apps/admin_web/public/guide/<id>.png 로 저장한다.
박스 위치는 DOM 요소의 실제 좌표에서 읽는다. 화면이 바뀌면 다시 돌리고 배포한다(시트는 같은 주소를 =IMAGE로 불러온다).
사용: scripts/run_all.sh 를 띄운 뒤 uv run --with playwright python scripts/capture_guide.py [화면id ...]  (설치된 Chrome 사용)"""
import json, os, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = os.path.join(os.path.dirname(__file__), "..", "apps", "admin_web", "public", "guide")
os.makedirs(OUT, exist_ok=True)

def T(sel, text=None, nth=0, up=None):
    return {"sel": sel, "text": text, "nth": nth, "up": up}

# (번호, 찾을 요소, 이름, 설명)
SCREENS = [
    {"id": "01-home", "title": "홈", "path": "/", "items": [
        (1, T("nav.sidebar"), "왼쪽 메뉴", "운영 · 활용 지원 · 관리 메뉴. 숫자 배지는 처리할 건수입니다."),
        (2, T("section[aria-label='핵심 지표']"), "핵심 지표 카드", "이번 달 비용(예산 대비) · 이용권 배정 · 승인 대기 등. 카드를 누르면 해당 화면으로 갑니다."),
        (3, T("section", "지금 확인할 일", up=None), "지금 확인할 일", "비용 급증 알림, 담당자 승인, 이용권 확인처럼 오늘 처리할 일. 한 줄을 누르면 그 화면으로 이동합니다."),
        (4, T("section", "모델별 API 비용"), "모델별 API 비용 · 예산 대비", "8월 / 9월 / 10월 탭으로 달을 바꿔 모델별 API 비용과 예산을 비교합니다."),
        (5, T("a", "AI 비서에게 모델 검토 요청"), "[AI 비서에게 모델 검토 요청] 버튼", "AI 비서 화면으로 이동해 더 싼 모델로 바꿀 수 있는지 검토를 요청합니다."),
        (6, T("section", "구독 중인 제품"), "구독 중인 제품", "계약한 제품별 과금 방식 · 이용권 · 이번 달 비용 · 갱신일. [전체 보기]는 구독·이용권 화면으로 갑니다."),
        (7, T("a.ask"), "[AI 비서에게 묻기] 버튼", "어느 화면에서든 AI 비서로 바로 갑니다."),
        (8, T("button.signout"), "로그아웃", "로그인 화면으로 돌아갑니다."),
    ]},
    {"id": "02-inbox", "title": "승인 대기", "path": "/inbox", "items": [
        (1, T("button[role=tab]", "승인 대기", up="[role=tablist]"), "[승인 대기] / [처리 이력] 탭", "결정이 필요한 요청과 이미 처리한 요청을 나눠 봅니다."),
        (2, T("section[aria-label='처리 요청 목록']"), "처리 요청 목록", "결정할 요청 목록. 하나를 누르면 오른쪽에 상세가 열립니다."),
        (3, T("section.detail"), "요청 상세 · AI 검토 의견", "진행 단계(요청 접수 → AI 의견 → 관리자 승인 → 실행·안내), 연두색 띠의 AI 권고, 변경 내용, 참고한 데이터를 봅니다."),
        (4, T("button", "반려"), "[반려] 버튼", "사유를 입력하고 [반려 확정]을 누르면 신청자에게 결과가 갑니다."),
        (5, T("button", "승인하고 실행"), "[승인하고 실행] 버튼", "실행 직전에 서버가 상태를 다시 확인한 뒤 실행합니다. 위험도가 높은 건은 [결정 기록]으로 바뀝니다."),
        (6, T("section", "AI 비서 처리 확인"), "AI 비서 처리 확인", "AI 비서가 실제 변경 직전에 멈춘 건. 확인하면 이어서 처리합니다. [새로 고침]으로 목록 갱신."),
    ]},
    {"id": "03-licenses", "title": "구독·이용권", "path": "/licenses", "items": [
        (1, T("button.prod-tab", up="div"), "제품 탭", "제품을 고르면 아래 내용이 그 제품 기준으로 바뀝니다."),
        (2, T("section[aria-label$='이용권 요약']"), "이용권 요약", "과금 방식 · 계약 좌석 · 배정 · 미배정 · 본인 확인 필요 좌석 수."),
        (3, T("button.chip", "전체", up="div"), "필터 버튼", "전체 / 장기 미사용 / 휴직 중 / 사용 기록 없음 / 최근 입사로 목록을 거릅니다."),
        (4, T("section.col-3 table"), "확인이 필요한 이용권 표", "직원 · 상태 · 마지막 사용 · 사용 의사 확인 여부. 사용 기록이 없다는 이유만으로 회수하지 않습니다."),
        (5, T("button", "본인 확인 요청"), "[본인 확인 요청] 버튼", "그 직원에게 Slack으로 사용 의사(계속 사용 / 반납 / 휴직)를 묻습니다."),
        (6, T("section", "이용권 신청"), "이용권 신청", "최근 신청과 처리 결과(바로 배정 / 승인 대기)."),
        (7, T("section[aria-label='처리 규칙']"), "처리 규칙", "좌석이 있으면 바로 배정, 없으면 AI 의견과 함께 승인 대기 등 규칙 요약."),
    ]},
    {"id": "04-seats", "title": "좌석 배치도", "path": "/seats", "click": "button.desk.check", "items": [
        (1, T("[role=tablist][aria-label='층']"), "층 탭", "5층 / 4층 / 3층을 바꿔 봅니다. 숫자는 그 층 인원."),
        (2, T("[role=group][aria-label='도구로 강조']"), "도구 버튼", "도구를 고르면 그 도구를 쓰는 자리만 진하게 보입니다."),
        (3, T(".legend"), "범례", "재직 / 휴직(빗금) / 이용권 확인 필요(점선) / 최근 30일 사용일 막대."),
        (4, T("button.desk[aria-pressed='true']"), "책상", "이름 · 쓰는 도구 로고 · 최근 30일 사용일. 누르면 오른쪽에 상세가 나옵니다."),
        (5, T("aside.detail"), "직원 상세", "쓸 수 있는 도구, 마지막 사용일, 이용권 상태."),
        (6, T("aside.detail a", "구독·이용권에서 확인하기"), "[구독·이용권에서 확인하기] 버튼", "확인이 필요한 직원이면 구독·이용권 화면으로 이어집니다."),
    ]},
    {"id": "05-cost", "title": "비용·사용량", "path": "/cost", "items": [
        (1, T("button.chip", "배", up="div"), "알림 고르기", "비용 급증 알림이 여러 개면 여기서 고릅니다. '확인 전'은 아직 처리하지 않은 알림."),
        (2, T("section[aria-label='비용 급증 알림']"), "비용 급증 알림", "감지 시각, 기준(직전 14일 중앙값) 대비 몇 배인지, 하루 비용."),
        (3, T("section", "일별 비용"), "일별 비용 그래프", "기준선과 비교한 최근 일별 비용."),
        (4, T("aside"), "AI 조사 결과", "AI가 정리한 원인 후보와 참고한 데이터. 아직 조사 전이면 [AI 조사 실행]을 누릅니다. 원인은 확정이 아닌 후보입니다."),
        (5, T("fieldset.actions"), "대응 선택", "반복 요청 점검·부서 확인 요청 / 예산 검토 / 품질 평가 후 모델 검토 중 하나를 고릅니다."),
        (6, T("button", "처리 요청 만들기"), "[처리 요청 만들기] 버튼", "고른 대응으로 처리 요청을 만들어 승인 대기로 보냅니다."),
        (7, T("a", "AI 비서에게 더 묻기"), "[AI 비서에게 더 묻기] 버튼", "이 알림에 대한 질문이 채워진 채로 AI 비서가 열립니다."),
        (8, T("section", "프로젝트별 이번 달 비용"), "프로젝트별 이번 달 비용", "프로젝트 · 모델 · 환경 · 예산 대비 · 상태 표."),
    ]},
    {"id": "06-suggestions", "title": "자동 제안 기록", "path": "/suggestions", "items": [
        (1, T("section[aria-label='이번 주 요약']"), "이번 주 요약", "수집한 업데이트 · 팀에 보낸 제안 · 보내지 않음 · 도움 됨 반응 비율."),
        (2, T("section.col-3 table"), "업데이트별 팀 결과", "업데이트마다 어느 팀에 보냈고, 보내지 않았다면 왜인지(판단 이유)."),
        (3, T("a", "공식 원문"), "[공식 원문] 링크", "제품사의 릴리스 노트 원문을 엽니다."),
        (4, T("section", "팀별 자동 발송"), "팀별 자동 발송", "팀별 스위치. 끄면 그 팀에는 보내지 않고 기록만 남깁니다(지금은 보기만 됨)."),
        (5, T("section[aria-label='알림 정책']"), "알림 정책", "팀당 주 2건, 평일 09~18시, 관련 근거가 있을 때만 보냅니다."),
    ]},
    {"id": "07-needs", "title": "미지원 요청·팀 활용", "path": "/needs", "items": [
        (1, T("section", "미지원 요청"), "미지원 요청", "승인 제품으로 할 수 없었던 직원 요청. 같은 기능 3건 이상 · 2개 부서 이상이면 '검토' 표시."),
        (2, T("section", "팀별 활용 현황"), "팀별 활용 현황", "5명 이상 팀 단위로만 봅니다. 개인 지표는 보이지 않습니다."),
        (3, T("a", "자동 제안 기록 보기"), "[자동 제안 기록 보기] 버튼", "자동 제안 기록 화면으로 이동합니다."),
    ]},
    {"id": "08-assistant", "title": "AI 비서", "path": "/assistant", "items": [
        (1, T("button.chip", "조사해줘", up="div"), "예시 질문", "누르면 입력창에 채워집니다. 처음 쓸 때 참고하세요."),
        (2, T("input.ask-input"), "질문 입력창", "자연어로 요청합니다. 예: '박지후 님 ChatGPT 이용권 배정해줘'."),
        (3, T("label.new-thread"), "[새 대화로 시작]", "체크하면 앞 대화와 이어지지 않는 새 대화로 보냅니다."),
        (4, T("button", "보내기"), "[보내기] 버튼", "보내면 진행 상황(조회 중 · 답변 작성 중)이 실시간으로 보입니다."),
        (5, T("section", "내 요청"), "내 요청", "보낸 요청의 상태(완료 · 승인 대기 · 실패)와 답변 기록."),
    ]},
    {"id": "09-setup", "title": "회사 설정", "path": "/setup", "items": [
        (1, T("ol.stepper"), "설정 단계", "① 부서·직원 ② 구독 제품 ③ AI 모델·프로젝트 ④ 연간 예산 ⑤ 확인. 눌러서 바로 이동."),
        (2, T("button", "부서 추가", up="form"), "새 부서 이름 + [부서 추가]", "부서를 하나씩 추가합니다."),
        (3, T("textarea"), "직원 붙여넣기", "엑셀에서 '이름, 이메일, 부서, 직함'을 복사해 붙입니다. 잘못된 줄은 줄 번호와 함께 알려 줍니다."),
        (4, T("button", "명 추가"), "[직원 N명 추가] 버튼", "붙여 넣은 직원을 한 번에 등록합니다."),
        (5, T("button", "다음:"), "[다음] 버튼", "다음 단계로 넘어갑니다. 마지막 단계에서 [설정 마치고 홈으로]."),
    ]},
    {"id": "10-login", "title": "로그인", "path": "/login", "logout": True, "items": [
        (1, T("ol.features"), "기능 소개", "F1~F4 핵심 기능 요약."),
        (2, T("#login-id", up="label"), "사번 또는 이메일", "사번(예: emp_mkt_01) 또는 회사 이메일."),
        (3, T("#login-pw", up="label"), "비밀번호 + [보기]", "[보기]로 입력한 비밀번호를 확인합니다. 5번 틀리면 5분 잠금."),
        (4, T("button[type=submit]"), "[로그인] 버튼", "로그인하면 1시간 유지됩니다."),
        (5, T(".demo"), "시연 계정", "개발 서버 전용. 누르면 비밀번호 없이 그 계정으로 들어갑니다(관리자 2명 · 직원 2명)."),
    ]},
]

FIND = """q => { let els = [...document.querySelectorAll(q.sel)];
  if (q.text) els = els.filter(e => (e.innerText || e.value || '').replace(/\\s+/g, ' ').includes(q.text));
  if (q.sel === 'section' && q.text) els = els.filter(e => !e.querySelector('section') || (e.querySelector('h2') || {}).innerText?.includes(q.text));
  let e = els[q.nth || 0]; if (!e) return null; if (q.up) e = e.closest(q.up) || e;
  const r = e.getBoundingClientRect(); return {x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height} }"""

DRAW = """({n, r}) => { const pad = 4, c = '#E5484D';
  const b = document.createElement('div');
  Object.assign(b.style, {position: 'absolute', left: (r.x - pad) + 'px', top: (r.y - pad) + 'px', width: (r.w + pad * 2) + 'px', height: (r.h + pad * 2) + 'px',
    border: '3px solid ' + c, borderRadius: '10px', boxSizing: 'border-box', zIndex: 99999, pointerEvents: 'none'});
  const s = document.createElement('div'); s.textContent = n;
  const lx = r.x - pad - 14 < 2 ? r.x - pad + 4 : r.x - pad - 14, ty = r.y - pad - 14 < 2 ? r.y - pad + 4 : r.y - pad - 14;
  Object.assign(s.style, {position: 'absolute', left: lx + 'px', top: ty + 'px', width: '28px', height: '28px', borderRadius: '50%', background: c, color: '#fff',
    font: '700 15px/28px system-ui, sans-serif', textAlign: 'center', zIndex: 100000, boxShadow: '0 0 0 2px #fff'});
  document.body.style.position = 'relative'; document.body.append(b, s); }"""

tok = json.load(urllib.request.urlopen(urllib.request.Request(
    "http://localhost:8000/auth/login", data=b'{"login_id":"emp_asset_01","password":"demo1234"}',
    headers={"content-type": "application/json"})))["data"]["access_token"]
only = set(sys.argv[1:])
meta, missing = [], []
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    for sc in SCREENS:
        if only and sc["id"] not in only:
            continue
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pg = ctx.new_page()
        pg.goto(BASE + "/login")
        if not sc.get("logout"):
            pg.evaluate("t => localStorage.setItem('token', t)", tok)
        pg.goto(BASE + sc["path"]); pg.wait_for_timeout(2500)
        if sc.get("click"):
            pg.locator(sc["click"]).first.click(); pg.wait_for_timeout(600)
        for n, q, name, desc in sc["items"]:
            r = pg.evaluate(FIND, q)
            if not r:
                missing.append(f"{sc['id']} #{n} {name}"); continue
            pg.evaluate(DRAW, {"n": n, "r": r})
        path = os.path.join(OUT, sc["id"] + ".png")
        pg.screenshot(path=path, full_page=True)
        h = pg.evaluate("document.documentElement.scrollHeight")
        meta.append({**{k: sc[k] for k in ("id", "title", "path")}, "height": h,
                     "items": [{"n": n, "name": name, "desc": d} for n, _, name, d in sc["items"]]})
        ctx.close()
    b.close()
json.dump(meta, open(os.path.join(OUT, "guide.json"), "w"), ensure_ascii=False, indent=1)
print("missing:", missing or "none")
