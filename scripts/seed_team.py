"""실제 Slack 계정 6명으로 테스트 회사를 만든다. 개발 DB의 app 스키마를 지우고, 시드 대신 셋팅 기능(REST)을 차례로 불러 채운다.

사용: uv run python scripts/seed_team.py --yes
  - 관리자(웹 콘솔 로그인)는 최승우 한 명. 비밀번호는 TEAM_ADMIN_PASSWORD, 없으면 새로 만들어 한 번 출력한다.
  - 나머지 5명은 Slack으로만 쓴다(비밀번호 없음). Slack 봇은 DB의 slack_user_id로 직원을 찾는다(.env SLACK_USER_MAP={}).
  - 기존 사원·신입 모두 이용권은 본인이 신청해야 받는다. 여기서는 '이미 쓰던 회사'라 좌석 일부만 CSV로 넣어 둔다.
테스트하기 좋게 남겨 둔 상태:
  - ChatGPT Enterprise 5석 중 4석 배정 → 첫 신청은 관리자 승인 뒤 배정, 좌석이 없으면 반려(추가 구매 없음)
  - Acrobat Pro 2석 모두 배정 → 신청하면 관리자 승인, 정서현은 40일 미사용(반납·회수 시험용)
  - 정윤지 ChatGPT 좌석은 사용 기록 없음(확인 필요) → 사용 의사 확인 요청 시험용
  - 이용주는 F3 시연 좌석(.env F3_DEMO_HEAVY에 이메일)
"""

from __future__ import annotations

import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

DOMAIN = "hanbit.example"
ADMIN = ("최승우", "U0CAZ73D1NG", "seungwoo.choi", "HRD", "자산관리 담당 · 과장")
# 이름, Slack 회원 ID, 이메일 앞부분, 부서, 직무 · 직급, 등록 업무(제목, 설명, 주기, 쓰는 제품)
TEAM = [
    ("이용주", "U0CAP67KQKV", "yongju.lee", "마케팅", "브랜드 마케팅 · 대리",
     ("경쟁사 보도자료 비교", "경쟁사 보도자료 여러 건을 비교해 메시지 차이를 정리", "weekly", ["ChatGPT Enterprise"])),
    ("유정연", "U0CBLALS88H", "jeongyeon.yoo", "영업", "영업 담당 · 사원",
     ("견적서 요약 검토", "고객 견적서 PDF를 요약해 영업 메모로 정리", "daily", ["Acrobat Pro"])),
    ("정서현", "U0CAF7Z7PRD", "seohyun.jung", "고객지원", "CS 상담 · 주임",
     ("응대 매뉴얼 갱신", "자주 묻는 문의를 모아 응대 매뉴얼 문구를 고침", "weekly", ["ChatGPT Enterprise", "Claude API"])),
    ("정윤지", "U0CARE0JF29", "yunji.jung", "상품기획·MD", "상품기획 · 과장",
     ("신제품 고객 리뷰 분석", "온라인몰·SNS 리뷰 파일 여러 개에서 불만·요청을 분류해 기획 보고서에 반영", "weekly", ["ChatGPT Enterprise"])),
    ("채석현", "U0CAF8HD3L7", "seokhyun.chae", "생산관리", "생산 계획 · 대리",
     ("생산 일정 변경 공지", "라인별 일정 변경 사항을 공지문으로 정리", "weekly", [])),
]
YEAR = date.today().year
CONTRACTS = [
    {"vendor": "OpenAI", "product": "ChatGPT Enterprise", "category": "chat_assistant", "plan_name": "ChatGPT Enterprise", "billing_type": "seat_plus_usage",
     "seats_purchased": 5, "seat_price_krw": 45000, "daily_token_quota": 150_000},
    {"vendor": "Anthropic", "product": "Claude API", "category": "llm_api", "plan_name": "API pay-as-you-go", "billing_type": "api_usage",
     "seats_purchased": 0, "seat_price_krw": 0},
    {"vendor": "Adobe", "product": "Acrobat Pro", "category": "pdf_editor", "kind": "software", "allowed_data_class": "confidential",
     "plan_name": "Acrobat Pro for teams", "billing_type": "seat_flat", "seats_purchased": 2, "seat_price_krw": 32000},
]
MODELS = ["anthropic:claude-opus-5-5", "anthropic:claude-sonnet-5-5", "anthropic:claude-haiku-5-5", "openai:gpt-5.5", "openai:gpt-5.5-mini"]


def _day(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


# 이미 쓰던 좌석 (CSV 가져오기). 마지막 사용일을 비우면 '기록 없음(확인 필요)'
SEATS = {
    "ChatGPT Enterprise": [("yongju.lee", _day(1)), ("seohyun.jung", _day(1)), ("yunji.jung", ""), ("seungwoo.choi", _day(1))],
    "Acrobat Pro": [("jeongyeon.yoo", _day(1)), ("seohyun.jung", _day(40))],
}


def _ok(r):
    body = r.json()
    if "error" in body:
        raise SystemExit(f"{r.request.method} {r.request.url.path} 실패: {body['error']}")
    return body["data"]


def reset_schema() -> None:
    from apps.backend import db
    with db.engine.begin() as c:
        c.connection.driver_connection.execute((ROOT / "db/schema.sql").read_text(encoding="utf-8"))


def build(client, system_token: str, admin_password: str) -> dict:
    """빈 app 스키마에서 셋팅 기능을 차례로 불러 회사를 만든다. 테스트(tests/test_seed_team.py)도 이 함수를 쓴다."""
    from apps.backend import db
    name, slack, local, dept, title = ADMIN
    adm = _ok(client.post("/setup/signup", json={"company_name": "한빛제조", "admin_name": name, "email": f"{local}@{DOMAIN}",
                                                  "password": admin_password, "dept_name": dept, "job_title": title}))
    A = {"Authorization": f"Bearer {adm['access_token']}"}
    with db.tx() as c:  # 가입 화면에는 Slack 회원 ID 칸이 없다 (직원 수정 API도 아직 없음)
        c.execute(db.text("UPDATE employees SET slack_user_id = :s WHERE id = :id"), dict(s=slack, id=adm["employee"]["id"]))
    for d in dict.fromkeys(t[3] for t in TEAM):
        if d != dept:
            _ok(client.post("/departments", json={"name": d}, headers=A))
    depts = {d["name"]: d["id"] for d in _ok(client.get("/departments", headers=A))}
    _ok(client.post("/employees", headers=A, json=[{"name": n, "email": f"{lo}@{DOMAIN}", "dept_id": depts[d], "job_title": t, "slack_user_id": s,
                                                    "hire_date": _day(400 + 90 * i)} for i, (n, s, lo, d, t, _) in enumerate(TEAM)]))
    products = {}
    for body in CONTRACTS:
        ctr = _ok(client.post("/contracts", headers=A, json={**body, "term_start": f"{YEAR}-01-01", "term_end": f"{YEAR}-12-31"}))
        products[body["product"]] = ctr
    catalog = {m["id"] for m in _ok(client.get("/setup/model-catalog", headers=A))}
    _ok(client.put("/models/approved", headers=A, json={"model_ids": [m for m in MODELS if m in catalog]}))
    from apps.backend import fixtures as fx  # 평가 결과는 평가 실행기(후속) 몫이라 API가 없다. 공식 시드 값을 그대로 쓴다
    with db.tx() as c:
        for r in fx.EVAL_RESULTS:
            if r.model_id in MODELS:
                c.execute(db.text("INSERT INTO eval_results (id, task_type, model_id, quality_score, threshold, passed, avg_input_tokens, avg_output_tokens, latency_ms, evaluated_at)"
                                  " VALUES (:id, :tt, :m, :q, :th, :p, :i, :o, :l, :at)"),
                          dict(id=r.id, tt=r.task_type, m=r.model_id, q=r.quality_score, th=r.threshold, p=r.passed, i=r.avg_input_tokens,
                               o=r.avg_output_tokens, l=r.latency_ms, at=r.evaluated_at))
    people = {e["email"]: e for e in _ok(client.get("/org/members", headers=A)) for e in [e["employee"]]}
    owner = people[f"seohyun.jung@{DOMAIN}"]
    _ok(client.post("/projects", headers=A, json={"name": "고객 문의 분류", "dept_id": owner["dept_id"], "owner_id": owner["id"],
                                                  "purpose": "고객 문의를 유형별로 자동 분류", "model_id": "anthropic:claude-sonnet-5-5", "environment": "prod", "monthly_budget_krw": 300000}))
    budget = _ok(client.get("/budgets", headers=A))
    _ok(client.put("/budgets", headers=A, json={"fiscal_year": budget["fiscal_year"], "seat_annual_krw": 3_600_000, "api_annual_krw": 6_000_000}))
    for product, rows in SEATS.items():
        csv = "email,last_activity_at\n" + "\n".join(f"{lo}@{DOMAIN},{d}" for lo, d in rows)
        _ok(client.post(f"/contracts/{products[product]['id']}/seats/import", headers=A, json={"csv": csv}))
    tool_of = {t["product"]: t["id"] for t in _ok(client.get("/tools", headers=A))}
    S = {"Authorization": f"Bearer {system_token}"}
    for _, s, _, _, _, (t_title, desc, freq, uses) in TEAM:  # 등록 업무는 본인만 쓴다 → Slack 봇과 같은 방식으로 본인 토큰을 받는다
        tok = _ok(client.post("/auth/slack-exchange", headers=S, json={"slack_user_id": s, "employee_id": None}))["access_token"]
        _ok(client.post("/me/tasks", headers={"Authorization": f"Bearer {tok}"},
                        json={"title": t_title, "description": desc, "frequency": freq, "tools_used": [tool_of[u] for u in uses]}))
    for d, did in depts.items():  # 4층에 부서마다 책상 2개, 사람을 앉힌다
        desks = _ok(client.post("/desks", headers=A, json={"floor": "4F", "dept_id": did, "count": 2}))
        members = [e for e in people.values() if e["dept_id"] == did and e["role"] != "system"]
        for desk, e in zip(desks, members):
            _ok(client.put(f"/desks/{desk['id']}", headers=A, json={"employee_id": e["id"]}))
    _ok(client.post("/internal/jobs/collect_usage/run", headers=S))  # 좌석 사용량 더미 (F3 평균 기준)
    _ok(client.post("/setup/complete", headers=A))
    inv = {i["tool_name"]: f"{i['assigned']}/{i['purchased']}석" for i in _ok(client.get("/inventory", headers=A))}
    staff = [e for e in people.values() if e["role"] != "system"]
    return {"employees": len(staff), "admins": [e["name"] for e in staff if e["role"] == "admin"], "seats": inv}


def main() -> None:
    import os

    if "--yes" not in sys.argv:
        raise SystemExit("개발 DB의 app 스키마를 지우고 6명 회사로 다시 만듭니다. 계속하려면 --yes 를 붙이세요.")
    from fastapi.testclient import TestClient

    from apps.backend.main import app
    password = os.getenv("TEAM_ADMIN_PASSWORD") or secrets.token_urlsafe(9)
    if len(password) < 8:  # 가입 API가 거절하면 스키마만 지워진 채 끝난다. 지우기 전에 막는다
        raise SystemExit("TEAM_ADMIN_PASSWORD는 8자 이상이어야 합니다. DB는 건드리지 않았습니다.")
    reset_schema()
    out = build(TestClient(app), os.getenv("SYSTEM_TOKEN", "dev.sys"), password)
    print("만들었습니다:", out)
    print(f"웹 콘솔 로그인: {ADMIN[2]}@{DOMAIN}" + ("" if os.getenv("TEAM_ADMIN_PASSWORD") else f" / 비밀번호 {password} (이번 한 번만 보여 줍니다)"))
    print(".env: SLACK_USER_MAP={} · SLACK_ADMIN_USER_IDS=" + ADMIN[1] + f" · F3_DEMO_HEAVY=yongju.lee@{DOMAIN}")


if __name__ == "__main__":
    main()
