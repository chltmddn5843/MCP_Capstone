"""API 호출과 에이전트 스트림 렌더링. 화면 파일들이 공유한다."""

from __future__ import annotations

import json
import os

import requests
import streamlit as st

from apps.admin_ui import labels as L

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")
AGENT = os.getenv("AGENT_URL", "http://localhost:8002")


def hdr() -> dict:
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}


def _down(base: str, exc: Exception) -> None:
    name = "백엔드" if base == BACKEND else "에이전트"
    st.error(f"{name} 서버({base})에 연결할 수 없습니다. `scripts/run_all.sh`로 먼저 실행하세요. ({type(exc).__name__})")


def api(method: str, path: str, base: str = BACKEND, quiet: bool = False, **kw):
    try:
        r = requests.request(method, base + path, headers={**hdr(), **kw.pop("headers", {})}, timeout=30, **kw)
        body = r.json()
    except requests.exceptions.RequestException as exc:
        _down(base, exc)
        return None
    except ValueError:
        st.error(f"{method} {path}: 서버 응답을 읽을 수 없습니다 (HTTP {r.status_code})")
        return None
    if "error" in body:
        if not quiet:
            e = body["error"]
            st.error(f"{L.ERROR_CODE.get(e['code'], e['code'])}: {e['message']}")
        return None
    return body["data"]


def login(employee_id: str) -> bool:
    try:
        r = requests.post(f"{BACKEND}/auth/dev-login", json={"employee_id": employee_id}, timeout=10).json()
    except requests.exceptions.RequestException as exc:
        _down(BACKEND, exc)
        return False
    if "error" in r:
        st.error(r["error"]["message"])
        return False
    st.session_state.token, st.session_state.me = r["data"]["access_token"], r["data"]["employee"]
    st.session_state.pop("thread_id", None)
    return True


def start_task(text: str, prompt_name: str | None = None, prompt_args: dict | None = None, new_thread: bool = False) -> str | None:
    created = api("POST", "/ai/tasks", base=AGENT, json={"input": text, "prompt_name": prompt_name, "prompt_args": prompt_args or {},
                                                        "thread_id": None if new_thread else st.session_state.get("thread_id"), "channel": "admin_ui"})
    if not created:
        return None
    st.session_state.thread_id = created["thread_id"]
    return created["task_id"]


def render_stream(task_id: str, after: int = 0) -> None:
    """진행 이벤트를 사용자 언어로 그린다. 승인 대기·완료·실패에서 멈춘다."""
    status = st.status("AI 비서가 처리하고 있습니다…", expanded=True)
    answer_box, answer = st.empty(), ""
    try:
        resp = requests.get(f"{AGENT}/ai/tasks/{task_id}/stream", params={"after": after}, headers=hdr(), stream=True, timeout=180)
    except requests.exceptions.RequestException as exc:
        _down(AGENT, exc)
        return
    with resp as r:
        for raw in r.iter_lines():
            line = raw.decode() if isinstance(raw, bytes) else raw
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            t = ev["type"]
            if t == "TOKEN":
                answer += ev["text"]
                answer_box.markdown(answer)
            elif t == "TOOL_START":
                status.write(f"🔎 {L.TOOL.get(ev['tool_call']['name'], ev['tool_call']['name'])} 중…")
            elif t == "TOOL_END":
                tc = ev["tool_call"]
                label = L.TOOL.get(tc["name"], tc["name"])
                if tc.get("error"):
                    msg = tc["error"]
                    try:
                        code = json.loads(tc.get("output") or "{}").get("error", {}).get("code")
                        msg = L.ERROR_CODE.get(code, msg)
                    except Exception:  # noqa: BLE001
                        pass
                    status.write(f"⚠️ {label}: {msg}")
                else:
                    status.write(f"✅ {label} 완료")
            elif t == "APPROVAL_REQUIRED":
                status.update(label="담당자 승인 대기", state="error", expanded=True)
                card = ev["approval"]
                st.warning(f"**관리자 확인이 필요한 단계입니다.** {card['summary']}")
                st.caption("관리자가 '승인 대기'에서 확인하면 이어서 자동 처리됩니다. 결과는 '내 요청'에서 볼 수 있습니다.")
                return
            elif t == "DONE":
                status.update(label="완료", state="complete", expanded=False)
                res = ev["result"]
                answer_box.markdown(res["answer"])
                if res.get("evidence"):
                    with st.expander(f"참고한 데이터 {len(res['evidence'])}건"):
                        for e in res["evidence"]:
                            st.markdown(f"- **{L.TOOL.get(e['source'], e['source'])}** · `{e['ref']}`")
                return
            elif t == "FAILED":
                status.update(label="실패", state="error")
                st.error(f"처리 중 문제가 생겼습니다: {ev['error']}")
                return


def assistant_panel(role: str, title: str = "AI 비서") -> None:
    """역할별 추천 질문 + 자유 입력 + 스트림."""
    st.subheader(title)
    cols = st.columns(len(L.QUICK_PROMPTS.get(role, [])) or 1)
    chosen = None
    for col, q in zip(cols, L.QUICK_PROMPTS.get(role, [])):
        if col.button(q, key=f"qp_{role}_{q[:12]}", width="stretch"):
            chosen = q
    c1, c2 = st.columns([5, 1])
    typed = c1.text_input("무엇을 도와드릴까요?", key=f"ask_{role}", placeholder="업무를 설명하거나 요청을 적어 주세요")
    new_thread = c2.checkbox("새 대화", key=f"new_{role}", help="체크하지 않으면 이전 대화를 이어갑니다")
    send = st.button("보내기", type="primary", key=f"send_{role}")
    text = chosen or (typed if send else None)
    if text:
        tid = start_task(text, new_thread=new_thread or chosen is not None)
        if tid:
            render_stream(tid)


def task_history(mine: bool = True, limit: int = 10) -> None:
    st.subheader("내 요청")
    tasks = api("GET", "/ai/tasks", base=AGENT, params={"mine": mine, "limit": limit}) or []
    if not tasks:
        st.caption("아직 요청이 없습니다.")
    for t in tasks:
        label = f"{t['created_at'][5:16].replace('T', ' ')} · {L.TASK_STATUS.get(t['status'], t['status'])} · {t['input'][:40]}"
        with st.expander(label):
            if t.get("result"):
                st.markdown(t["result"]["answer"])
            if t["status"] == "waiting_approval" and t.get("approval"):
                st.warning(f"담당자 승인 대기: {t['approval']['summary']}")
            if t.get("error"):
                st.error(t["error"])
            st.caption("처리 단계: " + " → ".join(L.TOOL.get(tc["name"], tc["name"]) + (" ⚠️" if tc.get("error") else "") for tc in t["tool_calls"]) or "없음")


def approval_inbox(me: dict) -> None:
    """승인 대기: 처리 요청 결정 + AI 비서 처리 확인. 관리자가 쓴다."""
    st.subheader("승인 대기 요청")
    st.caption("'담당자 승인' 요청은 승인하면 처리됩니다. '책임자 결정' 요청(구매, 운영 환경 변경)은 결정만 기록하고 처리는 시스템 밖에서 합니다.")
    page = api("GET", "/plans", params={"status": "pending_approval"})
    items = (page or {}).get("items", [])
    for p in items:
        with st.container(border=True):
            st.markdown(f"**{L.PLAN_TYPE.get(p['type'], p['type'])}** · {L.RISK.get(p['risk_level'], p['risk_level'])} · 요청자 `{p['requested_by']}`")
            st.write(p["rationale"])
            with st.expander("대상과 참고한 데이터"):
                st.json({"대상": p["items"], "참고한 데이터": p["evidence"]}, expanded=True)
            reason = st.text_input("결정 사유 (필수)", key=f"r_{p['id']}")
            c1, c2 = st.columns(2)
            if c1.button("승인", key=f"a_{p['id']}", type="primary") and api("POST", f"/plans/{p['id']}/approve", json={"reason": reason}):
                st.success("승인했습니다.")
                st.rerun()
            if c2.button("반려", key=f"j_{p['id']}") and api("POST", f"/plans/{p['id']}/reject", json={"reason": reason}):
                st.success("반려했습니다.")
                st.rerun()
    if not items:
        st.caption("승인 대기 중인 요청이 없습니다.")

    st.subheader("AI 비서 처리 확인")
    st.caption("AI 비서가 실제 변경을 하기 직전에 멈춘 건입니다. 확인하면 그 지점부터 이어서 처리합니다.")
    tasks = api("GET", "/ai/tasks", base=AGENT, params={"mine": False}, quiet=True) or []
    waiting = [t for t in tasks if t["status"] == "waiting_approval"]
    for t in waiting:
        card = t["approval"]
        with st.container(border=True):
            st.markdown(f"**{card['summary']}**")
            st.caption(f"요청: {t['input']} · 요청자 `{t['requester_id']}` · 단계: {L.TOOL.get(card['tool_name'], card['tool_name'])}")
            reason = st.text_input("결정 사유 (필수)", key=f"tr_{t['task_id']}")
            c1, c2 = st.columns(2)
            after = len(t["tool_calls"]) * 2 + 1
            if c1.button("확인하고 처리", key=f"ta_{t['task_id']}", type="primary") and api("POST", f"/ai/tasks/{t['task_id']}/approval", base=AGENT, json={"approved": True, "reason": reason}):
                render_stream(t["task_id"], after=after)
            if c2.button("거절", key=f"tj_{t['task_id']}") and api("POST", f"/ai/tasks/{t['task_id']}/approval", base=AGENT, json={"approved": False, "reason": reason}):
                render_stream(t["task_id"], after=after)
    if not waiting:
        st.caption("확인을 기다리는 AI 비서 작업이 없습니다.")
