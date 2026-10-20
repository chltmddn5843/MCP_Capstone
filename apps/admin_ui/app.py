"""관리자 화면 (Streamlit). 메인 · 자산 관리 · 승인함 · 에이전트.
실행: uv run streamlit run apps/admin_ui/app.py
"""

from __future__ import annotations

import json
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")
AGENT = os.getenv("AGENT_URL", "http://localhost:8002")
SEED_USERS = {"emp_asset_01": "최민준 · 자산관리", "emp_hrd_01": "김하나 · HRD", "emp_approver_01": "정수아 · 승인자", "emp_mkt_01": "박서준 · 마케팅 직원", "emp_cs_01": "이지우 · CS 직원"}
LABEL = {"pending_approval": "승인 대기", "approved": "승인", "executed": "실행", "rejected": "반려", "failed": "실패", "draft": "초안",
         "low": "낮음", "medium": "중간", "high": "높음", "unused": "미사용", "on_leave": "휴직", "no_record": "기록 없음(확인 필요)", "recent_hire": "최근 입사"}

st.set_page_config(page_title="AI 활용·운영 최적화", layout="wide")


# ---------- API ----------
def hdr() -> dict:
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}


def api(method: str, path: str, base: str = BACKEND, **kw):
    r = requests.request(method, base + path, headers={**hdr(), **kw.pop("headers", {})}, timeout=30, **kw)
    body = r.json()
    if "error" in body:
        st.error(f"{body['error']['code']}: {body['error']['message']}")
        return None
    return body["data"]


def login(employee_id: str) -> None:
    r = requests.post(f"{BACKEND}/auth/dev-login", json={"employee_id": employee_id}, timeout=10).json()
    st.session_state.token = r["data"]["access_token"]
    st.session_state.me = r["data"]["employee"]


# ---------- 에이전트 스트림 ----------
def run_agent(text: str, prompt_name: str | None = None, prompt_args: dict | None = None, thread_id: str | None = None) -> str | None:
    created = api("POST", "/ai/tasks", base=AGENT, json={"input": text, "prompt_name": prompt_name, "prompt_args": prompt_args or {}, "thread_id": thread_id, "channel": "admin_ui"})
    if not created:
        return None
    st.session_state.thread_id = created["thread_id"]
    return created["task_id"]


def render_stream(task_id: str, after: int = 0) -> None:
    """SSE를 읽어 TOKEN·TOOL·APPROVAL·DONE을 그린다. 종료 이벤트에서 멈춘다."""
    status = st.status("에이전트 실행 중…", expanded=True)
    answer_box = st.empty()
    answer = ""
    with requests.get(f"{AGENT}/ai/tasks/{task_id}/stream", params={"after": after}, headers=hdr(), stream=True, timeout=180) as r:
        for raw in r.iter_lines():
            line = raw.decode() if isinstance(raw, bytes) else raw
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            st.session_state.last_seq = ev["seq"]
            t = ev["type"]
            if t == "TOKEN":
                answer += ev["text"]
                answer_box.markdown(answer)
            elif t == "TOOL_START":
                status.write(f"🔧 `{ev['tool_call']['name']}` 호출 중… 입력: `{json.dumps(ev['tool_call']['input'], ensure_ascii=False)[:120]}`")
            elif t == "TOOL_END":
                tc = ev["tool_call"]
                status.write(("⚠️ " if tc.get("error") else "✅ ") + f"`{tc['name']}` 결과: `{(tc.get('output') or '')[:160]}`")
            elif t == "APPROVAL_REQUIRED":
                status.update(label="승인 대기", state="error", expanded=True)
                st.session_state.pending_task = task_id
                card = ev["approval"]
                st.warning(f"**승인 필요** — {card['summary']}\n\n도구: `{card['tool_name']}` · plan_id: `{card.get('plan_id')}`")
                st.info("승인함 탭에서 승인·거절하면 이어서 실행됩니다.")
                return
            elif t == "DONE":
                status.update(label="완료", state="complete", expanded=False)
                res = ev["result"]
                answer_box.markdown(res["answer"])
                if res.get("evidence"):
                    with st.expander(f"근거 {len(res['evidence'])}건"):
                        st.json(res["evidence"])
                return
            elif t == "FAILED":
                status.update(label="실패", state="error")
                st.error(ev["error"])
                return


# ---------- 사이드바 ----------
with st.sidebar:
    st.title("한빛제조 AI 운영")
    who = st.selectbox("로그인 (시드 직원)", list(SEED_USERS), format_func=lambda k: SEED_USERS[k])
    if st.button("로그인", width='stretch') or "token" not in st.session_state:
        login(who)
    me = st.session_state.me
    st.caption(f"{me['name']} · {me['role']} · {me.get('dept_name', '')}")
    st.caption(f"backend {BACKEND}\nagent {AGENT}")

tab_main, tab_asset, tab_inbox, tab_agent = st.tabs(["메인", "자산 관리", "승인함", "에이전트"])

# ---------- 메인 ----------
with tab_main:
    st.subheader("활용 지표 (팀 단위)")
    if me["role"] == "hrd":
        rows = api("GET", "/adoption/teams")
        if rows:
            st.dataframe([{"팀": r["team_name"], "인원": r["headcount"], "제안": r["suggestions_sent"], "도움 됨": r["useful"], "관련 없음": r["irrelevant"], "질문": r["questions"], "활동 비율": f"{r['active_ratio']:.0%}"} for r in rows], width='stretch')
    else:
        st.caption("활용 지표는 HRD 역할만 봅니다.")
    st.subheader("미충족 수요")
    if me["role"] in ("hrd", "asset", "approver"):
        aggs = api("GET", "/unmet-needs")
        if aggs:
            st.dataframe([{"태그": a["capability_tag"], "건수": a["count"], "부서 수": a["dept_count"], "기준 충족": "예" if a["threshold_met"] else "아니오", "예시": " / ".join(a["sample_summaries"])} for a in aggs], width='stretch')
            for a in aggs:
                if a["threshold_met"] and st.button(f"'{a['capability_tag']}' 후보 비교 요청", key=f"cmp_{a['capability_tag']}"):
                    tid = run_agent(f"{a['capability_tag']} 수요에 대한 후보 제품을 비교해줘", "compare_candidates", {"capability_tag": a["capability_tag"]})
                    if tid:
                        render_stream(tid)
    st.subheader("최근 업데이트")
    page = api("GET", "/updates")
    if page:
        for u in page["items"]:
            st.markdown(f"- **{u['vendor']}** {u['title']} — {u['summary']} [원문]({u['url']})")

# ---------- 자산 관리 ----------
with tab_asset:
    if me["role"] not in ("asset", "approver", "system"):
        st.caption("자산 관리 화면은 자산관리·승인자 역할만 봅니다.")
    else:
        st.subheader("이용권 현황")
        for inv in api("GET", "/inventory") or []:
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{inv['tool_name']} 구매", inv["purchased"])
            c2.metric("배정", inv["assigned"])
            c3.metric("미배정", inv["unassigned"])
            st.dataframe([{"직원": c["employee_name"], "부서": c["dept_name"], "마지막 활동": c["last_activity_at"] or "-", "분류": LABEL.get(c["flag"], c["flag"]), "확인 필요": "예" if c["needs_confirmation"] else "아니오"} for c in inv["low_usage_candidates"]], width='stretch')
        st.subheader("사용량 경보")
        if me["role"] == "asset":
            for a in api("GET", "/anomalies") or []:
                with st.container(border=True):
                    st.markdown(f"**{a['scope_name']}** · 기준 대비 **{a['ratio']}배** · 예상 월 비용 {a['projected_monthly_cost']['krw']:,}원 · 상태 {a['status']}")
                    if st.button("조사 시작", key=f"inv_{a['id']}"):
                        tid = run_agent(f"경보 {a['id']}의 원인을 조사하고 조치안을 제안해줘", "investigate_anomaly", {"anomaly_id": a["id"]})
                        if tid:
                            render_stream(tid)
        sv = api("GET", "/savings")
        if sv:
            st.subheader("절감 기록")
            st.write({LABEL.get(k, k): f"{v:,}원" for k, v in sv["by_kind"].items()} | {"합계": f"{sv['total_krw']:,}원"})

# ---------- 승인함 ----------
with tab_inbox:
    st.subheader("조치안 승인")
    page = api("GET", "/plans", params={"status": "pending_approval"})
    for p in (page or {}).get("items", []):
        with st.container(border=True):
            st.markdown(f"**{p['type']}** · 위험도 {LABEL.get(p['risk_level'])} · 요청자 `{p['requested_by']}`\n\n{p['rationale']}")
            st.json(p["items"], expanded=False)
            reason = st.text_input("사유 (필수)", key=f"r_{p['id']}")
            c1, c2 = st.columns(2)
            if c1.button("승인", key=f"a_{p['id']}") and api("POST", f"/plans/{p['id']}/approve", json={"reason": reason}):
                st.success("승인됨")
                st.rerun()
            if c2.button("반려", key=f"j_{p['id']}") and api("POST", f"/plans/{p['id']}/reject", json={"reason": reason}):
                st.success("반려됨")
                st.rerun()
    if not (page or {}).get("items"):
        st.caption("승인 대기 조치안이 없습니다.")
    st.subheader("에이전트 실행 승인 (변경 도구)")
    tasks = api("GET", "/ai/tasks", base=AGENT, params={"mine": me["role"] == "employee"}) or []
    waiting = [t for t in tasks if t["status"] == "waiting_approval"]
    for t in waiting:
        card = t["approval"]
        with st.container(border=True):
            st.markdown(f"**{card['summary']}**\n\n요청: {t['input']} · 요청자 `{t['requester_id']}` · 도구 `{card['tool_name']}`")
            st.json(card["tool_input"], expanded=False)
            reason = st.text_input("사유 (필수)", key=f"tr_{t['task_id']}")
            c1, c2 = st.columns(2)
            if c1.button("승인하고 실행", key=f"ta_{t['task_id']}") and api("POST", f"/ai/tasks/{t['task_id']}/approval", base=AGENT, json={"approved": True, "reason": reason}):
                render_stream(t["task_id"], after=len(t["tool_calls"]) * 2 + 1)
            if c2.button("거절", key=f"tj_{t['task_id']}") and api("POST", f"/ai/tasks/{t['task_id']}/approval", base=AGENT, json={"approved": False, "reason": reason}):
                render_stream(t["task_id"], after=len(t["tool_calls"]) * 2 + 1)
    if not waiting:
        st.caption("승인 대기 중인 에이전트 작업이 없습니다.")

# ---------- 에이전트 ----------
with tab_agent:
    st.subheader("에이전트에게 요청")
    st.caption(f"thread: `{st.session_state.get('thread_id', '새 대화')}`")
    c1, c2 = st.columns([5, 1])
    text = c1.text_input("요청", placeholder="예: 박서준 님 AI-A 이용권 배정해줘 / 내 등록 업무 알려줘 / 견적서 요약 프로젝트 비용이 왜 늘었어?")
    new_thread = c2.checkbox("새 대화", value=False)
    if st.button("보내기", type="primary") and text:
        tid = run_agent(text, thread_id=None if new_thread else st.session_state.get("thread_id"))
        if tid:
            render_stream(tid)
    st.subheader("내 작업 이력")
    for t in (api("GET", "/ai/tasks", base=AGENT, params={"mine": True}) or [])[:10]:
        with st.expander(f"{t['created_at'][:19]} · {t['status']} · {t['input'][:40]}"):
            st.write(f"도구 호출 {len(t['tool_calls'])}회 · 턴 {t['turns']} · trace `{t['trace_id']}`")
            if t.get("result"):
                st.markdown(t["result"]["answer"])
            if t.get("error"):
                st.error(t["error"])
