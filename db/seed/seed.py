"""시드 SQL을 표준 출력으로 낸다. fixtures.py의 id를 그대로 넣고(계약 테스트), 시연용 더미를 덧붙인다.

사용: uv run python db/seed/seed.py | docker compose exec -T postgres psql -U capstone -d capstone
(보통은 db/reset.sh가 스키마와 함께 한 번에 넣는다)
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 저장소 루트 (apps.backend.fixtures)
from apps.backend import fixtures as fx  # noqa: E402

ARRAY_COLS = {"tools_used", "affected_plans", "sent_dept_ids"}
JSON_COLS = {"items", "evidence", "result", "before", "after", "held", "payload"}
random.seed(7)  # 매번 같은 더미


def lit(col: str, v) -> str:
    if v is None:
        return "NULL"
    if col in JSON_COLS:
        return "'" + json.dumps(v, ensure_ascii=False, default=str).replace("'", "''") + "'::jsonb"
    if col in ARRAY_COLS:
        return "'{" + ",".join(f'"{x}"' for x in v) + "}'"
    if isinstance(v, Enum):
        v = v.value
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return f"'{v.isoformat()}'"
    return "'" + str(v).replace("'", "''") + "'"


def insert(table: str, rows: list[dict]) -> None:
    for r in rows:
        cols = ", ".join(r)
        vals = ", ".join(lit(c, v) for c, v in r.items())
        print(f"INSERT INTO {table} ({cols}) VALUES ({vals});")


def dump(objs, drop=(), **extra) -> list[dict]:
    """pydantic 응답 모델 → 행. drop: 파생 필드(테이블에 없는 것)."""
    out = []
    for o in objs:
        d = o.model_dump(mode="python")
        for k in drop:
            d.pop(k, None)
        d.update(extra)
        out.append(d)
    return out


NOW = fx.NOW
DAY0 = NOW - timedelta(days=60)
print("SET search_path TO app;\nBEGIN;")

# ── 조직 ──
slack = {"dept_hrd": "C_HRD", "dept_mkt": "C_MKT", "dept_sales": "C_SALES", "dept_cs": "C_CS", "dept_prod": "C_PROD", "dept_mgmt": "C_MGMT"}
insert("departments", [{**d, "slack_channel_id": slack[d["id"]], "suggestions_enabled": d["id"] != "dept_prod"}
                       for d in dump(fx.DEPARTMENTS.values())])

SURNAMES = "김이박최정강조윤장임한오서신권황안송류홍"
GIVEN = ["민서", "지호", "서연", "도현", "하은", "준우", "예린", "시우", "수아", "건우", "지안", "유준", "다은", "현우", "채원", "승민"]
TITLES = {"dept_mgmt": "경영지원", "dept_hrd": "교육 운영", "dept_mkt": "마케터", "dept_sales": "영업 담당", "dept_cs": "CS 상담", "dept_prod": "생산 계획"}
gen_emps = []
for i in range(1, 55):  # AI-A 60석 중 58석 배정 (fixtures와 같은 수치)
    dept = list(TITLES)[i % 6]
    gen_emps.append({"id": f"emp_gen_{i:03d}", "name": random.choice(SURNAMES) + random.choice(GIVEN),
                     "email": f"user{i:03d}@hanbit.example", "dept_id": dept, "role": "employee",
                     "job_title": TITLES[dept], "status": "on_leave" if i in (7, 23) else "active",
                     "hire_date": (NOW - timedelta(days=20 if i in (52, 53, 54) else 400 + i * 9)).date()})
insert("employees", dump(fx.EMPLOYEES.values(), drop=("dept_name",)) + gen_emps)
humans = [e for e in list(fx.EMPLOYEES) + [g["id"] for g in gen_emps] if e != "sys"]

# ── 제품·계약·모델 ──
insert("tools", dump(fx.TOOLS.values(), kind="ai") + [
    {"id": "tool_adobe", "kind": "software", "vendor": "Adobe", "product": "Acrobat Pro", "category": "pdf_editor",
     "approval_status": "approved", "allowed_data_class": "confidential", "policy_note": "계약서 PDF 편집·비교. AI 불필요 업무 안내용"}])
insert("contracts", dump(fx.CONTRACTS.values()) + [
    {"id": "ctr_adobe_2026", "tool_id": "tool_adobe", "plan_name": "Acrobat Pro Teams", "billing_type": "seat_flat",
     "seats_purchased": 60, "seat_price_krw": 32000, "term_start": date(2026, 1, 1), "term_end": date(2026, 12, 31)}])
insert("models", dump(fx.MODELS.values(), tool_id="tool_ai_b"))
insert("eval_results", dump(fx.EVAL_RESULTS))
insert("registered_tasks", dump(fx.TASKS.values()))

# ── F1 ──
insert("vendor_sources", [
    {"id": "src_ai_a_rn", "vendor": "AI-A", "url": "https://vendor-a.example/release-notes", "kind": "release_notes"},
    {"id": "src_ai_b_rn", "vendor": "AI-B", "url": "https://vendor-b.example/release-notes", "kind": "release_notes"},
    {"id": "src_x_docs", "vendor": "Vendor-X", "url": "https://vendor-x.example/docs", "kind": "docs", "is_candidate": True}])
insert("vendor_updates", dump(fx.UPDATES.values()))
sugs = []
for s in dump(fx.SUGGESTIONS.values()):
    tid = s.pop("target_id")
    s["target_employee_id" if s["target_type"] == fx.TargetType.employee else "target_dept_id"] = tid
    sugs.append(s)
sugs.append({"id": "sug_002", "update_id": "upd_ai_a_doc_compare", "target_type": "team", "target_dept_id": "dept_prod",
             "relevance": "생산관리팀 등록 업무에 문서 비교 근거 없음", "body": "-", "status": "on_hold",
             "hold_reason": "관련 업무 근거 없음 · 팀 자동 발송 꺼짐"})
insert("suggestions", sugs)
insert("feedback", [{"id": "fb_001", "suggestion_id": "sug_001", "employee_id": "emp_hrd_01", "reaction": "useful", "created_at": NOW}])
insert("review_runs", [{"id": "rr_001", "update_id": "upd_ai_a_doc_compare", "agent_task_id": "task_demo_001", "ran_at": NOW,
                        "sent_dept_ids": ["dept_hrd"], "held": [{"dept_id": "dept_prod", "reason": "근거 없음"}]}])

# ── F3 ──
insert("projects", dump(fx.PROJECTS.values()))
insert("api_keys", [{"id": f"key_{p}", "project_id": p, "label": f"{p} 운영 키", "vendor_key_ref": f"vk_{p}", "created_at": DAY0}
                    for p in fx.PROJECTS])
usage = []
base_reqs = {"prj_cs_classify": 1000, "prj_quote_summary": 2100, "prj_faq": 60}
for d in range(60):
    day = DAY0 + timedelta(days=d)
    for pid, reqs in base_reqs.items():
        p = fx.PROJECTS[pid]
        m = fx.MODELS[p.model_id]
        spike = pid == "prj_quote_summary" and d >= 57  # 마지막 3일 비용 급증 (anm_001)
        r = int(reqs * random.uniform(0.85, 1.15) * (1.6 if spike else 1))
        tin, tout = r * (4200 if spike else 1500), r * 300
        usd = round(tin / 1e6 * m.input_usd_per_mtok + tout / 1e6 * m.output_usd_per_mtok, 4)
        usage.append({"vendor_record_id": f"vr_{pid}_{d:02d}", "contract_id": "ctr_ai_b_2026", "period_start": day,
                      "project_id": pid, "api_key_id": f"key_{pid}", "model_id": p.model_id,
                      "input_length_bucket": "4-16k" if spike else "1-4k", "requests": r, "input_tokens": tin,
                      "output_tokens": tout, "cost_usd": usd, "fx_rate": fx.FX, "cost_krw": round(usd * fx.FX)})
insert("usage_records", usage)
anm = dump(fx.ANOMALIES.values(), drop=("scope_name",))
for a in anm:
    cost = a.pop("projected_monthly_cost")
    a["projected_monthly_krw"], a["projected_monthly_usd"] = (cost["krw"], cost["usd"]) if cost else (None, None)
insert("anomalies", anm)

# ── F4 ── AI-A 60석 중 배정 58석(emp_mkt_01은 신청 대기), Adobe 60석 중 20석
seats = []
for i, e in enumerate(x for x in humans if x != "emp_mkt_01"):
    flag, last = None, NOW - timedelta(days=random.randint(0, 6))
    if e in ("emp_sales_02", "emp_gen_007", "emp_gen_023"):
        flag, last = "on_leave", NOW - timedelta(days=50)
    elif i % 9 == 0:
        flag, last = "unused", NOW - timedelta(days=45)
    elif i % 13 == 0:
        flag, last = "no_record", None  # 기록 없음 = 확인 필요
    elif e in ("emp_gen_052", "emp_gen_053", "emp_gen_054"):
        flag = "recent_hire"
    seats.append({"id": f"seat_a_{i:03d}", "contract_id": "ctr_ai_a_2026", "employee_id": e, "status": "assigned",
                  "assigned_at": DAY0, "last_activity_at": last, "flag": flag})
for i, e in enumerate(humans[:20]):
    seats.append({"id": f"seat_ad_{i:03d}", "contract_id": "ctr_adobe_2026", "employee_id": e, "status": "assigned",
                  "assigned_at": DAY0, "last_activity_at": NOW - timedelta(days=random.randint(0, 30))})
insert("seat_assignments", seats)
insert("unmet_needs", dump(fx.UNMET_NEEDS))

# ── 처리 요청 · 절감 · 감사 ──
plans = dump(fx.PLANS.values())
for p in plans:
    if p["id"] == "plan_002":
        p["ai_opinion"] = "휴직자 좌석 재배정 권장. 대상자 사용 의사 확인 응답 후 실행"
insert("action_plans", plans)
insert("confirmations", dump(fx.CONFIRMATIONS.values()))
insert("savings_ledger", dump(fx.SAVINGS))
insert("audit_log", dump(fx.AUDIT))

# ── 운영 ── 재시도 시연용
insert("job_runs", [
    {"id": "job_001", "name": "collect_usage", "queue": "batch", "status": "done", "attempt": 1, "idempotency_key": "collect_usage:2026-10-20T08",
     "created_at": NOW - timedelta(hours=1), "finished_at": NOW - timedelta(minutes=59)},
    {"id": "job_002", "name": "collect_usage", "queue": "batch", "status": "done", "attempt": 3, "idempotency_key": "collect_usage:2026-10-20T08:30",
     "last_error": "503 from mock_vendor (2회 재시도 후 성공)", "created_at": NOW - timedelta(minutes=30), "finished_at": NOW - timedelta(minutes=28)},
    {"id": "job_003", "name": "send_suggestion", "queue": "notify", "status": "dead", "attempt": 3, "idempotency_key": "send_suggestion:sug_001",
     "payload": {"suggestion_id": "sug_001"}, "last_error": "Slack API timeout x3", "created_at": NOW - timedelta(minutes=10)}])

print("COMMIT;")
