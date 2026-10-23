"""Slack 메시지 형식 (설계 문서 9절 메시지 5종). 봇과 백엔드 워커(notify 큐)가 함께 쓴다.

워커 사용 예:
    from slack_sdk import WebClient
    from apps.slack_bot.send import send_suggestion
    send_suggestion(WebClient(token=SLACK_BOT_TOKEN), channel=dept.slack_channel_id, suggestion=s, task_title=..., update=u)
각 함수는 Block Kit blocks를 만들고 chat.postMessage를 호출한다. 텍스트만 필요하면 build_* 함수를 쓴다.
"""

from __future__ import annotations

from typing import Any

PLAN_TYPE = {"seat_assign": "이용권 배정", "seat_reclaim": "이용권 회수·재배정", "model_change": "모델 변경", "budget_review": "예산 검토", "purchase_review": "미도입 제품 신청"}


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _buttons(items: list[tuple[str, str, str, str | None]]) -> dict:
    """items: (label, action_id, value, style|None)"""
    els = []
    for label, action_id, value, style in items:
        b: dict[str, Any] = {"type": "button", "text": {"type": "plain_text", "text": label}, "action_id": action_id, "value": value}
        if style:
            b["style"] = style
        els.append(b)
    return {"type": "actions", "elements": els}


# ---------- 1. 활용 제안 (F1) ----------
MODEL_RELEASE = "새 모델 출시"


def build_model_card(suggestion: dict, update: dict, job_title: str | None = None) -> list[dict]:
    """새 모델 카드 뉴스: 제목 + 핵심 기능 3개 + '이렇게 써 보세요'는 **받는 사람 직무 줄만**. 카드에 그 직무가 없으면 공통 한 줄.
    전체 직무 목록은 관리자 화면(자동 제안 기록)에서만 본다. 카드 본문 형식은 prompt_draft_model_card.md가 정한다."""
    head, jobs, section = [], [], "feat"
    for line in suggestion["body"].splitlines():
        s = line.strip()
        if s in ("핵심 기능", "이렇게 써 보세요"):
            section = "jobs" if s == "이렇게 써 보세요" else "feat"
            if section == "feat":
                head.append(f"*{s}*")
            continue
        if section == "jobs":
            if s:
                jobs.append(s)
        elif s:
            head.append(line.rstrip())
    mine = [j for j in jobs if job_title and j.lstrip("•- ").startswith(job_title + ":")]
    if jobs:
        head.append("*이렇게 써 보세요*")
        head += [f"*{j}*  ← 내 직무" for j in mine] or ["• 내 직무 활용 예는 아직 없어요. 등록 업무를 적어 두면 다음 카드부터 맞춰 드려요."]
    cond = ", ".join(update.get("affected_plans") or []) or "회사 승인 제품"
    return [
        {"type": "header", "text": {"type": "plain_text", "text": update["title"][:150]}},
        _section("\n".join(head)),
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"쓸 수 있는 곳: {cond} · 사내 데이터 사용은 회사 정책을 따라요 · <{update.get('url', '')}|원문 보기>"}]},
        _buttons([("도움 됨", "fb_useful", suggestion["id"], "primary"), ("관련 없음", "fb_irrelevant", suggestion["id"], None), ("적용 방법 질문", "fb_question", suggestion["id"], None)]),
    ]


def build_suggestion(suggestion: dict, task_title: str | None, update: dict) -> list[dict]:
    head = f"*{task_title}* 업무에 쓸 수 있는 기능이 추가됐어요." if task_title else f"*{update.get('vendor', '')}* 에 새 기능이 추가됐어요."
    cond = ", ".join(update.get("affected_plans") or []) or "회사 플랜에서 사용 가능"
    return [
        _section(head),
        _section(suggestion["body"]),
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"적용 조건: {cond} · <{update.get('url', '')}|원문 보기>"}]},
        _buttons([("도움 됨", "fb_useful", suggestion["id"], "primary"), ("관련 없음", "fb_irrelevant", suggestion["id"], None), ("적용 방법 질문", "fb_question", suggestion["id"], None)]),
    ]


def send_suggestion(client, channel: str, suggestion: dict, task_title: str | None, update: dict, job_title: str | None = None) -> dict:
    if update.get("title", "").startswith(MODEL_RELEASE):
        blocks = build_model_card(suggestion, update, job_title)
        return client.chat_postMessage(channel=channel, text=update["title"], blocks=blocks)
    blocks = build_suggestion(suggestion, task_title, update)
    return client.chat_postMessage(channel=channel, text=suggestion["body"][:200], blocks=blocks)


# ---------- 3. 사용 의사 확인 (F4) ----------
def build_confirmation(confirmation: dict, tool_name: str, last_activity: str | None) -> list[dict]:
    status = f"마지막 사용 {last_activity[:10]}" if last_activity else "최근 사용 기록이 없습니다"
    return [
        _section(f"*{tool_name}* 이용권을 계속 사용하시나요?\n{status}. 반납하시면 필요한 동료에게 재배정됩니다. 응답이 없어도 회수되지 않습니다."),
        _buttons([("계속 필요", "cf_still_needed", confirmation["id"], "primary"), ("반납", "cf_return_seat", confirmation["id"], None), ("휴직·장기 부재", "cf_on_leave", confirmation["id"], None)]),
    ]


def send_confirmation(client, channel: str, confirmation: dict, tool_name: str, last_activity: str | None) -> dict:
    return client.chat_postMessage(channel=channel, text=f"{tool_name} 이용권 사용 여부를 확인해 주세요", blocks=build_confirmation(confirmation, tool_name, last_activity))


# ---------- 4. 승인 요청 (관리자 DM) ----------
def build_approval_request(task: dict, web_url: str | None = None) -> list[dict]:
    """관리자 알림. 상세와 결정은 웹 콘솔이 기본 창구이고, 버튼은 빠른 처리용이다."""
    card = task["approval"]
    link = f"\n<{web_url}|웹 콘솔에서 상세 보기·결정>" if web_url else ""
    opinion = task.get("opinion_summary")
    link = (f"\nAI 의견: {opinion}" if opinion else "") + link
    return [
        _section(f"*AI 비서 처리 확인 요청*\n{card['summary']}\n요청: {task['input']}\n요청자: `{task['requester_id']}`{link}"),
        _buttons([("확인하고 처리", "ap_yes", task["task_id"], "primary"), ("거절", "ap_no", task["task_id"], "danger")]),
    ]


def send_approval_request(client, channel: str, task: dict, web_url: str | None = None) -> dict:
    return client.chat_postMessage(channel=channel, text="AI 비서 처리 확인 요청", blocks=build_approval_request(task, web_url))


# ---------- 4-1. 처리 요청 승인 (관리자 DM, F4) ----------
def build_plan_request(plan: dict, who: str, product: str, web_url: str | None = None) -> list[dict]:
    """직원 신청이 승인 대기로 들어오면 관리자에게. 승인하면 실행까지, 결과 안내는 워커가 요청자에게 보낸다."""
    item = (plan.get("items") or [{}])[0]
    short = plan["type"] == "seat_assign" and is_short(plan)
    if plan["type"] == "seat_assign":
        head, what = "이용권 신청", "남은 좌석이 없어 승인할 수 없어요. 반려해 주세요. (추가 구매는 하지 않아요)" if short else "승인하면 남은 좌석에서 배정합니다."
    elif plan["type"] == "api_access":
        head, what = "API 사용 신청", f"용도: {item.get('purpose', '-')}\n승인하면 개인 테스트 프로젝트와 키를 만들고, 키는 본인만 한 번 볼 수 있는 링크로 보냅니다."
    elif plan["type"] == "seat_reclaim":
        head, what = "이용권 반납", "승인하면 좌석을 회수합니다."
    else:
        head, what = "처리 요청", plan.get("rationale", "")
    opinion = (plan.get("ai_opinion") or {}).get("summary")
    link = f"\n<{web_url}|웹 콘솔에서 자세히 보기>" if web_url else ""
    return [
        _section(f"*{head}* · {who} → {product}\n{what}" + (f"\nAI 의견: {opinion}" if opinion else "") + link),
        _buttons(([] if short else [("승인", "pl_yes", plan["id"], "primary")]) + [("반려", "pl_no", plan["id"], "danger")]),
    ]


def is_short(plan: dict) -> bool:
    """좌석 신청이 생성 때 남은 좌석 부족으로 표시됐는지 (근거의 inventory.shortage)."""
    return any(isinstance(e.get("value"), dict) and e["value"].get("shortage") for e in plan.get("evidence", []))


# ---------- 4-2. 이용권 메뉴 (F4, 규칙 경로: AI를 거치지 않는다) ----------
def build_menu(tools: list[dict], mine: set[str]) -> list[dict]:
    """tools: GET /tools (계약 있는 것만 버튼). mine: 지금 쓸 수 있는 제품 id(GET /me available_tools).
    좌석형은 쓰고 있으면 [반납], 아니면 [신청]. API형은 개인 권한이 따로 필요해 늘 [사용 신청] (용도를 묻는 창을 연다)."""
    blocks = [_section("*이용권 메뉴*\n버튼을 누르면 바로 신청돼요. 어떤 제품이 맞는지 모르겠으면 하고 싶은 일을 그냥 말씀해 주세요.")]
    for t in tools:
        c = t.get("contract")
        if not c or t.get("approval_status", "approved") != "approved":
            continue
        if c["billing_type"] == "api_usage":
            label, aid, value, note = "사용 신청", "menu_api_access", t["id"], "API · 용도를 적으면 관리자가 확인해요"
        elif t["id"] in mine:
            label, aid, value, note = "반납", "menu_seat_reclaim", c["id"], "쓰고 있어요"
        else:
            label, aid, value, note = "신청", "menu_seat_assign", c["id"], "관리자가 승인하면 배정돼요"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{t['product']}*\n{note}"},
                       "accessory": {"type": "button", "text": {"type": "plain_text", "text": label}, "action_id": aid, "value": value}})
    return blocks


def build_api_purpose_modal(tool_id: str, product: str, channel: str) -> dict:
    return {"type": "modal", "callback_id": "menu_api_submit", "private_metadata": f"{tool_id}|{channel}",
            "title": {"type": "plain_text", "text": "API 사용 신청"[:24]}, "submit": {"type": "plain_text", "text": "신청"},
            "close": {"type": "plain_text", "text": "취소"},
            "blocks": [{"type": "input", "block_id": "purpose", "label": {"type": "plain_text", "text": f"{product}를 어디에 쓰나요?"[:2000]},
                        "element": {"type": "plain_text_input", "action_id": "v", "max_length": 300,
                                    "placeholder": {"type": "plain_text", "text": "예: 고객 문의를 유형별로 자동 분류"}}}]}


# ---------- 5. 좌석 토큰 소비 경보 (F3, 본인에게만) ----------
SEAT_CHECKLIST = (  # PRD S2: 직원이 직접 할 수 있는 점검 행동. 완료 보고를 요구하지 않는다
    "긴 문서·대화를 통째로 다시 넣고 있지 않은지 점검해 보세요",
    "같은 질문을 여러 번 반복해서 보내고 있지 않은지 점검해 보세요",
    "간단한 작업에 무거운 모델을 쓰고 있지 않은지 점검해 보세요 (가벼운 모델로 충분할 수 있어요)",
)


def build_seat_alert(anomaly: dict) -> list[dict]:
    checks = "\n".join(f"• {c}" for c in SEAT_CHECKLIST)
    return [
        _section(f"*토큰 사용량이 많은 작업 중이에요!*\n지금 속도면 오늘 약 *{round(anomaly['observed']):,} 토큰*을 쓰게 돼요 "
                 f"(평소 평균 {round(anomaly['baseline']):,} 토큰의 *{anomaly['ratio']}배*).\n{checks}\n점검 결과를 따로 알려 주실 필요는 없어요."),
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "이 알림은 본인에게만 갑니다. 사용량은 이용권 관리에만 쓰고 인사평가에 쓰지 않습니다."}]},
        _buttons([("현재 작업 분석", "seat_analyze", anomaly["scope_id"], "primary")]),
    ]


def send_seat_alert(client, channel: str, anomaly: dict) -> dict:
    return client.chat_postMessage(channel=channel, text="토큰 사용량이 많은 작업 중이에요!", blocks=build_seat_alert(anomaly))


def build_cost_alert(teams: dict[str, int], link: str) -> list[dict]:
    """PRD S3: 관리자(HRD)에게 비용 이상 팀 요약과 대시보드 링크. 개인 이름은 쓰지 않는다."""
    rows = "\n".join(f"• {t}: {n}석" for t, n in sorted(teams.items(), key=lambda x: -x[1]))
    return [_section(f"*비용 이상 알림*\n평소보다 토큰을 2배 이상 빠르게 쓰는 좌석이 있는 팀이에요.\n{rows}\n"
                     f"<{link}|비용 관리 대시보드>에서 팀을 누르면 원인 분석과 대응 방법을 볼 수 있어요.")]


def send_cost_alert(client, channel: str, teams: dict[str, int], link: str) -> dict:
    return client.chat_postMessage(channel=channel, text="비용 이상 알림", blocks=build_cost_alert(teams, link))


# ---------- 2. 답변 (F2 등, 봇이 직접) ----------
def build_answer(result: dict) -> list[dict]:
    """Slack 답변은 자연어만. 참고 데이터(evidence)는 웹 콘솔과 로그에만 남긴다."""
    return [_section(result["answer"][:2900])]
