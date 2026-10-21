"""Slack 메시지 형식 (설계 문서 9절 메시지 5종). 봇과 백엔드 워커(notify 큐)가 함께 쓴다.

워커 사용 예:
    from slack_sdk import WebClient
    from apps.slack_bot.send import send_suggestion
    send_suggestion(WebClient(token=SLACK_BOT_TOKEN), channel=dept.slack_channel_id, suggestion=s, task_title=..., update=u)
각 함수는 Block Kit blocks를 만들고 chat.postMessage를 호출한다. 텍스트만 필요하면 build_* 함수를 쓴다.
"""

from __future__ import annotations

from typing import Any

PLAN_TYPE = {"seat_assign": "이용권 배정", "seat_reclaim": "이용권 회수·재배정", "model_change": "모델 변경", "budget_review": "예산 검토", "purchase_review": "구매 검토"}


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
def build_suggestion(suggestion: dict, task_title: str | None, update: dict) -> list[dict]:
    head = f"*{task_title}* 업무에 쓸 수 있는 기능이 추가됐어요." if task_title else f"*{update.get('vendor', '')}* 에 새 기능이 추가됐어요."
    cond = ", ".join(update.get("affected_plans") or []) or "회사 플랜에서 사용 가능"
    return [
        _section(head),
        _section(suggestion["body"]),
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"적용 조건: {cond} · <{update.get('url', '')}|원문 보기>"}]},
        _buttons([("도움 됨", "fb_useful", suggestion["id"], "primary"), ("관련 없음", "fb_irrelevant", suggestion["id"], None), ("적용 방법 질문", "fb_question", suggestion["id"], None)]),
    ]


def send_suggestion(client, channel: str, suggestion: dict, task_title: str | None, update: dict) -> dict:
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


# ---------- 5. 비용 급증 알림 (F3) ----------
def build_alert(anomaly: dict) -> list[dict]:
    cost = anomaly.get("projected_monthly_cost") or {}
    return [
        _section(f"*비용 급증 알림* · {anomaly.get('scope_name', anomaly['scope_id'])}\n기준 대비 *{anomaly['ratio']}배* · 예상 월 비용 {cost.get('krw', 0):,}원"),
        _buttons([("원인 조사", "al_investigate", anomaly["id"], "primary")]),
    ]


def send_alert(client, channel: str, anomaly: dict) -> dict:
    return client.chat_postMessage(channel=channel, text="비용 급증 알림", blocks=build_alert(anomaly))


# ---------- 2. 답변 (F2 등, 봇이 직접) ----------
def build_answer(result: dict) -> list[dict]:
    """Slack 답변은 자연어만. 참고 데이터(evidence)는 웹 콘솔과 로그에만 남긴다."""
    return [_section(result["answer"][:2900])]
