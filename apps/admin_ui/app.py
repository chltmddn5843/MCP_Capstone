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
from apps.admin_ui.common import AGENT, BACKEND, api, approval_inbox, assistant_panel, dev_login, login, logout, render_stream, start_task, task_history  # noqa: E402

load_dotenv()
SEED_USERS = {"emp_mkt_01": "박서준 · 마케팅 직원", "emp_cs_01": "이지우 · 고객지원 직원", "emp_hrd_01": "김하나 · HRD 직원",
              "emp_asset_01": "최민준 · 관리자"}

st.set_page_config(page_title="한빛제조 AI 활용·운영", layout="wide")

# ---------- 로그인 ----------
if "token" not in st.session_state:
    st.space("large")
    brand, form = st.columns([1.1, 1], gap="large", vertical_alignment="center")
    with brand:
        st.caption("한빛제조 · AI·구독 SW 운영")
        st.title("회사가 쓰는 AI를, 업무에 맞게")
        st.markdown("직원은 업무에 맞는 제품과 모델을 안내받고, 관리자는 이용권과 비용을 한 화면에서 챙깁니다.")
        st.space("small")
        for icon, title, desc in [(":material/campaign:", "업데이트 활용 제안", "새 기능 중 우리 팀 업무에 맞는 것만 골라 알려 줍니다"),
                                  (":material/tune:", "업무별 모델 추천", "품질 기준을 통과한 모델 중 비용이 낮은 것을 근거와 함께"),
                                  (":material/monitoring:", "비용 경보와 원인", "사용량이 튀면 원인 후보와 대응안을 먼저 정리합니다"),
                                  (":material/badge:", "이용권 운영", "남은 좌석은 바로 배정, 없으면 AI 의견과 함께 승인 대기")]:
            st.markdown(f"{icon} **{title}**  \n:gray[{desc}]")
    with form:
        with st.container(border=True):
            st.subheader("로그인")
            with st.form("login", border=False, enter_to_submit=True):
                login_id = st.text_input("사번 또는 회사 이메일", placeholder="예: emp_mkt_01", icon=":material/person:")
                password = st.text_input("비밀번호", type="password", icon=":material/key:")
                if st.form_submit_button("로그인", type="primary", width="stretch", icon=":material/login:"):
                    if not login_id.strip() or not password:
                        st.warning("사번(또는 이메일)과 비밀번호를 모두 입력하세요.")
                    elif login(login_id.strip(), password):
                        st.rerun()
            st.caption("5번 틀리면 5분 동안 잠깁니다. 로그인은 1시간 동안 유지됩니다.")
        if os.getenv("APP_ENV", "dev") != "prod":
            with st.expander("시연용 빠른 로그인", icon=":material/bolt:"):
                st.caption("개발 환경에서만 보입니다. 시드 계정 비밀번호는 db/seed/seed.py의 DEMO_PASSWORD입니다.")
                pick = st.pills("계정", list(SEED_USERS), format_func=lambda k: SEED_USERS[k], label_visibility="collapsed")
                if pick and dev_login(pick):
                    st.rerun()
    st.stop()

me = st.session_state.me
with st.sidebar:
    st.title("한빛제조 AI 활용·운영")
    st.markdown(f"**{me['name']}** · {me['job_title']}\n\n{me.get('dept_name', '')} · 역할: **{L.ROLE.get(me['role'], me['role'])}**")
    st.caption(L.ROLE_DESC.get(me["role"], ""))
    if st.button("로그아웃", icon=":material/logout:", width="stretch"):
        logout()
        st.rerun()
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


# ---------- 관리자 ----------
def admin_view() -> None:
    st.header("구독 운영 (관리자)")
    t_lic, t_cost, t_inbox, t_need, t_adopt, t_ask, t_hist = st.tabs(["이용권", "비용 급증 알림", "승인 대기", "미지원 요청", "활용 현황·자동 제안", "AI 비서", "내 요청"])
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
    with t_adopt:
        st.subheader("팀별 활용 현황")
        st.caption("개인이 특정되지 않도록 5명 이상 팀만, 팀 단위로만 보여 줍니다. 활용 데이터는 교육과 제품 개선에만 쓰고 인사평가에 쓰지 않습니다.")
        rows = api("GET", "/adoption/teams") or []
        if rows:
            st.dataframe([{"팀": r["team_name"], "인원": r["headcount"], "보낸 제안": r["suggestions_sent"], "도움 됨": r["useful"], "관련 없음": r["irrelevant"],
                           "적용 방법 질문": r["questions"], "AI 활동 인원 비율": f"{r['active_ratio']:.0%}", "반복 질문": " / ".join(r["top_questions"]) or "-"} for r in rows], width="stretch", hide_index=True)
        st.subheader("최근 제품 업데이트와 자동 제안")
        st.caption("허용 목록 벤더의 공식 릴리스 노트만 수집합니다. 새 항목이 있으면 시스템이 관련 팀을 판단해 알림 정책 안에서 팀 Slack으로 자동 발송합니다. '지금 검토'를 누르면 같은 판단을 바로 실행합니다.")
        for u in (api("GET", "/updates") or {}).get("items", []):
            with st.container(border=True):
                st.markdown(f"**{u['vendor']} · {u['title']}** ({u['published_at'][:10]})\n\n{u['summary']}  [원문 보기]({u['url']})")
                if st.button("지금 검토", key=f"rev_{u['id']}"):
                    tid = start_task(f"업데이트 {u['id']}를 검토해서 관련 팀 업무에 활용 제안을 만들어줘", "review_update", {"update_id": u["id"]}, new_thread=True)
                    if tid:
                        render_stream(tid)
        st.subheader("자동 제안 기록")
        st.caption("어느 팀에 뭘 보냈고, 왜 보내지 않았는지 남깁니다. (후속: 같은 내용을 HRD에 메일)")
        sugg = (api("GET", "/suggestions") or {}).get("items", [])
        if sugg:
            st.dataframe([{"업데이트": s_["update_id"], "대상": f"{s_['target_type']} {s_['target_id'] or ''}", "상태": L.SUGGESTION_STATUS.get(s_["status"], s_["status"]),
                           "보낸 이유": s_["relevance"] or "-", "보내지 않은 이유": s_.get("hold_reason") or "-"} for s_ in sugg], width="stretch", hide_index=True)
        else:
            st.caption("기록이 없습니다.")
    with t_ask:
        assistant_panel("admin")
    with t_hist:
        task_history()


{"employee": employee_view, "admin": admin_view}.get(role, employee_view)()
