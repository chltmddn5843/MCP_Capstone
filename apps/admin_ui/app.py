"""관리자·직원 화면 (Streamlit). 로그인한 역할에 따라 다른 화면을 보여 준다.
실행: uv run streamlit run apps/admin_ui/app.py   (백엔드 8000, 에이전트 8002가 떠 있어야 한다)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # 저장소 루트

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from apps.admin_ui import labels as L  # noqa: E402
from apps.admin_ui.common import AGENT, BACKEND, api, approval_inbox, assistant_panel, login, render_stream, start_task, task_history  # noqa: E402

load_dotenv()
SEED_USERS = {"emp_mkt_01": "박서준 · 마케팅 직원", "emp_cs_01": "이지우 · 고객지원 직원", "emp_hrd_01": "김하나 · HRD",
              "emp_asset_01": "최민준 · 자산관리", "emp_approver_01": "정수아 · IT·보안 책임자"}

st.set_page_config(page_title="한빛제조 AI 활용·운영", layout="wide")

# ---------- 로그인 ----------
with st.sidebar:
    st.title("한빛제조 AI 활용·운영")
    who = st.selectbox("사용자 선택 (시연용 로그인)", list(SEED_USERS), format_func=lambda k: SEED_USERS[k])
    if st.button("이 사용자로 로그인", width="stretch") or "token" not in st.session_state:
        if not login(who):
            st.stop()
    me = st.session_state.me
    st.markdown(f"**{me['name']}** · {me['job_title']}\n\n{me.get('dept_name', '')} · 역할: **{L.ROLE.get(me['role'], me['role'])}**")
    st.caption(L.ROLE_DESC.get(me["role"], ""))
    with st.expander("연결 정보"):
        st.caption(f"backend {BACKEND}\n\nagent {AGENT}")

role = me["role"]


# ---------- 직원 ----------
def employee_view() -> None:
    st.header(f"안녕하세요, {me['name']} 님")
    t_ask, t_mine, t_hist = st.tabs(["AI 비서", "내 업무와 이용권", "내 요청"])
    with t_ask:
        st.caption("업무를 설명하면 승인된 제품·모델 중에서 추천하고, 이용권 신청도 대신 접수합니다. 대화 내용은 저장하지 않고 주제와 요약만 남깁니다.")
        assistant_panel("employee")
    with t_mine:
        prof = api("GET", "/me")
        if prof:
            st.subheader("등록한 업무")
            st.caption("여기 등록된 업무를 기준으로 새 기능 제안과 모델 추천이 맞춰집니다. AI 비서에게 말하면 등록·수정할 수 있습니다.")
            if prof["tasks"]:
                st.dataframe([{"업무": t["title"], "설명": t["description"], "주기": t["frequency"], "사용 제품": ", ".join(t["tools_used"])} for t in prof["tasks"]], width="stretch", hide_index=True)
            else:
                st.caption("등록된 업무가 없습니다.")
            st.subheader("내가 쓸 수 있는 제품")
            st.dataframe([{"제품": t["product"], "제공사": t["vendor"], "플랜": (t.get("contract") or {}).get("plan_name", "-"),
                           "과금": L.BILLING.get((t.get("contract") or {}).get("billing_type", ""), "-"), "허용 데이터": t["allowed_data_class"], "유의사항": t.get("policy_note") or ""} for t in prof["available_tools"]], width="stretch", hide_index=True)
        st.subheader("내 신청 현황")
        page = api("GET", "/plans")
        rows = [{"신청": L.PLAN_TYPE.get(p["type"], p["type"]), "상태": L.PLAN_STATUS.get(p["status"], p["status"]), "내용": p["rationale"], "신청일": p["created_at"][:16].replace("T", " ")} for p in (page or {}).get("items", [])]
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.caption("신청 내역이 없습니다.")
    with t_hist:
        task_history()


# ---------- HRD ----------
def hrd_view() -> None:
    st.header("활용 지원 (HRD)")
    t_adopt, t_notice, t_ask, t_hist = st.tabs(["팀별 활용 현황", "자동 제안", "AI 비서", "내 요청"])
    with t_adopt:
        st.subheader("팀별 활용 현황")
        st.caption("개인이 특정되지 않도록 5명 이상 팀만, 팀 단위로만 보여 줍니다. 활용 데이터는 교육과 제품 개선에만 쓰고 인사평가에 쓰지 않습니다.")
        rows = api("GET", "/adoption/teams") or []
        if rows:
            st.dataframe([{"팀": r["team_name"], "인원": r["headcount"], "보낸 제안": r["suggestions_sent"], "도움 됨": r["useful"], "관련 없음": r["irrelevant"],
                           "적용 방법 질문": r["questions"], "AI 활동 인원 비율": f"{r['active_ratio']:.0%}", "반복 질문": " / ".join(r["top_questions"]) or "-"} for r in rows], width="stretch", hide_index=True)
            for r in rows:
                if r["top_questions"] and st.button(f"'{r['team_name']}' 직무 가이드 초안 만들기", key=f"guide_{r['team_id']}"):
                    tid = start_task(f"{r['team_name']} 팀의 반복 질문을 바탕으로 직무별 활용 가이드 초안을 써줘", "draft_role_guide", {"job_title": r["team_name"]}, new_thread=True)
                    if tid:
                        render_stream(tid)
        st.subheader("최근 AI 업데이트")
        st.caption("허용 목록 벤더의 공식 릴리스 노트만 수집합니다. '직원 업무에 연결'을 누르면 AI 비서가 관련 업무를 찾아 제안 초안을 만듭니다.")
        for u in (api("GET", "/updates") or {}).get("items", []):
            with st.container(border=True):
                st.markdown(f"**{u['vendor']} · {u['title']}** ({u['published_at'][:10]})\n\n{u['summary']}  [원문 보기]({u['url']})")
                if st.button("직원 업무에 연결", key=f"rev_{u['id']}"):
                    tid = start_task(f"업데이트 {u['id']}를 검토해서 관련 직원 업무에 활용 제안을 만들어줘", "review_update", {"update_id": u["id"]}, new_thread=True)
                    if tid:
                        render_stream(tid)
    with t_notice:
        st.subheader("팀·전사 공지 승인")
        st.caption("개인 맞춤 제안은 알림 정책 안에서 자동 발송되고, 팀·전사 공지만 HRD 승인을 거칩니다.")
        sugg = (api("GET", "/suggestions", params={"status": "pending_approval"}) or {}).get("items", [])
        for s in sugg:
            with st.container(border=True):
                st.markdown(f"**대상: {s['target_type']} {s['target_id'] or ''}** · 보내는 이유: {s['relevance']}")
                st.write(s["body"])
                if st.button("승인하고 발송", key=f"sa_{s['id']}") and api("POST", f"/suggestions/{s['id']}/approve"):
                    st.success("발송했습니다.")
                    st.rerun()
        if not sugg:
            st.caption("승인 대기 공지가 없습니다.")
        approval_inbox(me)
    with t_ask:
        assistant_panel("hrd")
    with t_hist:
        task_history()


# ---------- 자산관리 ----------
def asset_view() -> None:
    st.header("구독 운영 (관리자)")
    t_lic, t_cost, t_inbox, t_need, t_ask, t_hist = st.tabs(["이용권", "비용 급증 알림", "승인 대기", "미지원 요청", "AI 비서", "내 요청"])
    with t_lic:
        for inv in api("GET", "/inventory") or []:
            st.subheader(f"{inv['tool_name']} · {inv['contract']['plan_name']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("구매 좌석", inv["purchased"])
            c2.metric("배정", inv["assigned"])
            c3.metric("미배정", inv["unassigned"])
            c4.metric("좌석 단가 (월)", L.won(inv["contract"]["seat_price_krw"]))
            st.markdown("**확인이 필요한 이용권**")
            st.caption("사용 기록이 없다고 미사용으로 보지 않습니다. 본인에게 사용 의사를 묻고 반납 응답이 있을 때만 재배정합니다. 무응답은 회수 사유가 아닙니다.")
            st.dataframe([{"직원": c["employee_name"], "부서": c["dept_name"], "마지막 사용": (c["last_activity_at"] or "")[:10] or "기록 없음",
                           "상태": L.FLAG.get(c["flag"], c["flag"]), "본인 확인": "필요" if c["needs_confirmation"] else "불필요"} for c in inv["low_usage_candidates"]], width="stretch", hide_index=True)
        if st.button("안 쓰는 이용권 검토 요청", type="primary"):
            tid = start_task("안 쓰는 것으로 보이는 이용권을 검토해서 본인 확인이 필요한 사람과 재배정 가능한 좌석을 정리하고 처리 요청을 제안해줘", new_thread=True)
            if tid:
                render_stream(tid)
        sv = api("GET", "/savings")
        if sv:
            st.subheader("절감 기록")
            st.caption("아낀 구매 비용(재배정으로 안 산 좌석)과 실제로 줄어든 청구액을 구분해 기록합니다.")
            st.dataframe([{"구분": L.SAVINGS.get(k, k), "금액": L.won(v)} for k, v in sv["by_kind"].items()] + [{"구분": "합계", "금액": L.won(sv["total_krw"])}], width="stretch", hide_index=True)
    with t_cost:
        st.subheader("비용 급증 알림")
        st.caption("사용량을 원화로 환산해 기준치(최근 평균)의 몇 배인지 검사합니다. '원인 조사'를 누르면 AI 비서가 모델·입력 길이·API 키별로 나눠 원인 후보와 처리 방법을 제시합니다.")
        for a in api("GET", "/anomalies") or []:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**{a['scope_name']}** · 상태 {L.ANOMALY_STATUS.get(a['status'], a['status'])}")
                c2.metric("기준 대비", f"{a['ratio']}배")
                c3.metric("예상 월 비용", L.won(a["projected_monthly_cost"]["krw"]))
                if st.button("원인 조사", key=f"inv_{a['id']}", type="primary"):
                    tid = start_task(f"알림 {a['id']}의 원인을 조사하고 처리 방법을 제안해줘", "investigate_anomaly", {"anomaly_id": a["id"]}, new_thread=True)
                    if tid:
                        render_stream(tid)
    with t_need:
        st.subheader("미지원 요청")
        st.caption("승인 제품으로 할 수 없었던 직원 요청입니다. 같은 기능이 3건 이상, 2개 부서 이상이면 새 제품 도입을 검토할 때입니다.")
        aggs = api("GET", "/unmet-needs") or []
        if aggs:
            st.dataframe([{"필요한 기능": L.cap(a["capability_tag"]), "요청 수": a["count"], "요청한 부서 수": a["dept_count"], "도입 검토": "필요" if a["threshold_met"] else "아직",
                           "직원이 요청한 내용": " / ".join(a["sample_summaries"])} for a in aggs], width="stretch", hide_index=True)
        else:
            st.caption("기록된 요청이 없습니다.")
    with t_inbox:
        approval_inbox(me)
    with t_ask:
        assistant_panel("asset")
    with t_hist:
        task_history()


# ---------- 승인자 ----------
def approver_view() -> None:
    st.header("승인 대기 (책임자)")
    t_inbox, t_ask = st.tabs(["승인 대기", "AI 비서"])
    with t_inbox:
        approval_inbox(me)
    with t_ask:
        assistant_panel("approver")
        task_history()


{"employee": employee_view, "hrd": hrd_view, "asset": asset_view, "approver": approver_view}.get(role, employee_view)()
