"""Slack 봇 (Bolt, Socket Mode). 직원 접점.

수신: DM(message.im)과 멘션(app_mention) → 에이전트 작업 → 진행 상황을 한 메시지에 갱신 → 답변.
      승인이 필요하면 관리자에게 DM으로 확인 요청 버튼을 보내고, 결정 뒤 이어서 처리한다.
버튼: 제안 반응(도움 됨·관련 없음·질문) → 백엔드 /suggestions/{id}/feedback
      사용 의사(계속 필요·반납·휴직) → 백엔드 /confirmations/{id}/answer
      처리 확인(확인·거절) → 에이전트 /ai/tasks/{id}/approval
발신(제안·확인 요청·알림)은 백엔드 워커가 send.py의 함수로 보낸다. 이 프로세스는 수신만 한다.

실행: uv run python -m apps.slack_bot        (.env: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_USER_MAP, SLACK_ADMIN_USER_IDS)
점검: uv run python -m apps.slack_bot --check  (토큰·권한·채널 확인만 하고 종료)
"""

from __future__ import annotations

import logging
import os
import threading
import time

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from apps.slack_bot import client as api
from apps.slack_bot import identity
from apps.slack_bot.send import build_answer, build_approval_request

load_dotenv()
log = logging.getLogger("slack_bot")
TOOL_LABEL = {
    "get_my_profile": "내 정보와 등록 업무 확인", "list_approved_tools": "승인 제품·플랜 확인", "list_approved_models": "승인 모델·단가 확인",
    "get_eval_results": "모델 품질 평가 조회", "estimate_task_cost": "예상 비용 계산", "get_usage_summary": "사용량 조회",
    "get_license_inventory": "이용권 현황 조회", "record_unmet_need": "미지원 요청 기록", "create_action_plan": "처리 요청 작성",
    "get_plan_status": "처리 요청 상태 확인", "execute_approved_plan": "승인된 요청 처리", "search_vendor_docs": "제품 공식 문서 검색",
    "get_vendor_update": "업데이트 내용 확인", "search_internal_policy": "사내 정책 검색", "get_anomalies": "비용 급증 알림 조회",
    "get_anomaly_detail": "알림 상세 확인", "get_usage_breakdown": "사용량 세부 분석",
}
THREADS: dict[str, str] = {}  # slack (channel, thread_ts|user) -> agent thread_id. 같은 Slack 스레드면 같은 대화
PENDING: dict[str, dict] = {}  # task_id -> {"token", "channel", "ts", "thread_ts"} 승인 대기 중 복귀 정보


# ---------- 버튼 핸들러 (모듈 함수: 테스트에서 직접 부른다) ----------
def on_feedback(ack, body, action, client):
    ack()
    reaction = {"fb_useful": "useful", "fb_irrelevant": "irrelevant", "fb_question": "question"}[action["action_id"]]
    user = body["user"]["id"]
    try:
        token, _ = identity.resolve(user)
        api.feedback(token, action["value"], reaction)
        msg = {"useful": "도움이 됐다고 기록했어요. 감사합니다.", "irrelevant": "관련 없음으로 기록했어요. 같은 종류 제안은 줄일게요.",
               "question": "적용 방법을 알려드릴게요. 어떤 업무에 쓰려는지 DM으로 말씀해 주세요."}[reaction]
    except api.ApiError as exc:
        msg = f"기록하지 못했어요: {exc.message}"
    client.chat_postEphemeral(channel=body["channel"]["id"], user=user, text=msg)


def on_confirmation(ack, body, action, client):
    ack()
    answer = action["action_id"].removeprefix("cf_")
    user = body["user"]["id"]
    try:
        token, _ = identity.resolve(user)
        api.answer_confirmation(token, action["value"], answer)
        msg = {"still_needed": "계속 사용으로 기록했어요.", "return_seat": "반납으로 기록했어요. 관리자가 재배정합니다.", "on_leave": "휴직·장기 부재로 기록했어요."}[answer]
    except api.ApiError as exc:
        msg = f"기록하지 못했어요: {exc.message}"
    client.chat_postEphemeral(channel=body["channel"]["id"], user=user, text=msg)


def on_approval(ack, body, action, client):
    ack()
    approved = action["action_id"] == "ap_yes"
    task_id, user = action["value"], body["user"]["id"]
    try:
        token, emp = identity.resolve(user)
        if emp["role"] != "admin":
            client.chat_postEphemeral(channel=body["channel"]["id"], user=user, text="관리자만 확인할 수 있습니다.")
            return
        api.approve_task(token, task_id, approved, "Slack에서 " + ("확인" if approved else "거절"))
    except api.ApiError as exc:
        client.chat_postEphemeral(channel=body["channel"]["id"], user=user, text=f"처리하지 못했어요: {exc.message}")
        return
    client.chat_update(channel=body["channel"]["id"], ts=body["message"]["ts"], text=("확인하고 처리했습니다." if approved else "거절했습니다."), blocks=[])
    ctx = PENDING.pop(task_id, None)
    if ctx:  # 요청자 쪽 메시지를 이어서 갱신
        threading.Thread(target=_follow, args=(client, ctx["token"], task_id, ctx["channel"], ctx["ts"], ctx["thread_ts"], ctx["after"]), daemon=True).start()


def create_app(verify_token: bool = True) -> App:
    app = App(token=os.environ["SLACK_BOT_TOKEN"], token_verification_enabled=verify_token)

    @app.event("app_mention")
    def on_mention(event, client):
        _handle_request(client, event, _strip_mention(event.get("text", "")))

    @app.event("message")
    def on_message(event, client):
        if event.get("channel_type") != "im" or event.get("bot_id") or event.get("subtype"):
            return  # DM만, 봇 메시지·편집 제외
        _handle_request(client, event, event.get("text", ""))

    for aid in ("fb_useful", "fb_irrelevant", "fb_question"):
        app.action(aid)(on_feedback)
    for aid in ("cf_still_needed", "cf_return_seat", "cf_on_leave"):
        app.action(aid)(on_confirmation)
    for aid in ("ap_yes", "ap_no"):
        app.action(aid)(on_approval)
    return app


# ---------- 요청 처리 ----------
def _strip_mention(text: str) -> str:
    import re

    return re.sub(r"<@[A-Z0-9]+>", "", text).strip()


def _handle_request(client, event, text: str) -> None:
    channel, user = event["channel"], event["user"]
    thread_ts = event.get("thread_ts") or event.get("ts")
    if not text:
        return
    try:
        token, emp = identity.resolve(user)
    except api.ApiError as exc:
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"누구인지 확인하지 못했어요. {exc.message}")
        return
    key = f"{channel}:{thread_ts if event.get('channel_type') != 'im' else user}"
    try:
        created = api.create_task(token, text, THREADS.get(key))
    except api.ApiError as exc:
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"지금은 처리할 수 없어요: {exc.message}")
        return
    THREADS[key] = created["thread_id"]
    posted = client.chat_postMessage(channel=channel, thread_ts=thread_ts if event.get("channel_type") != "im" else None, text="AI 비서가 확인하고 있어요…")
    threading.Thread(target=_follow, args=(client, token, created["task_id"], channel, posted["ts"], posted.get("thread_ts"), 0), daemon=True).start()


def _follow(client, token: str, task_id: str, channel: str, ts: str, thread_ts: str | None, after: int) -> None:
    """SSE를 읽어 같은 메시지를 갱신한다 (chat.update는 1초에 1번만)."""
    steps: list[str] = []
    last_update = 0.0
    seq = after

    def update(text: str, blocks=None, force=False):
        nonlocal last_update
        if not force and time.time() - last_update < 1.0:
            return
        client.chat_update(channel=channel, ts=ts, text=text[:3000], blocks=blocks or [])
        last_update = time.time()

    try:
        for ev in api.stream_events(token, task_id, after=after):
            seq = ev["seq"]
            t = ev["type"]
            if t == "TOOL_START":
                steps.append(f"🔎 {TOOL_LABEL.get(ev['tool_call']['name'], ev['tool_call']['name'])} 중…")
                update("\n".join(steps[-4:]))
            elif t == "TOOL_END":
                tc = ev["tool_call"]
                label = TOOL_LABEL.get(tc["name"], tc["name"])
                steps[-1] = ("⚠️ " if tc.get("error") else "✅ ") + label
                update("\n".join(steps[-4:]))
            elif t == "APPROVAL_REQUIRED":
                update("관리자 확인을 기다리고 있어요. 확인되면 이어서 처리할게요.", force=True)
                PENDING[task_id] = {"token": token, "channel": channel, "ts": ts, "thread_ts": thread_ts, "after": seq}
                _notify_admins(client, token, task_id)
                return
            elif t == "DONE":
                update("완료", build_answer(ev["result"]), force=True)
                return
            elif t == "FAILED":
                update(f"처리 중 문제가 생겼어요: {ev['error']}", force=True)
                return
    except Exception as exc:  # noqa: BLE001
        log.exception("follow failed")
        update(f"진행 상황을 받지 못했어요: {exc}", force=True)


def _notify_admins(client, requester_token: str, task_id: str) -> None:
    try:
        task = api.agent("GET", f"/ai/tasks/{task_id}", requester_token)
    except api.ApiError as exc:
        log.warning("task fetch failed: %s", exc)
        return
    for admin in identity.admin_slack_ids():
        dm = client.conversations_open(users=admin)
        client.chat_postMessage(channel=dm["channel"]["id"], text="AI 비서 처리 확인 요청", blocks=build_approval_request(task))


# ---------- 점검 ----------
def check() -> int:
    from slack_sdk import WebClient

    bot, app_tok = os.getenv("SLACK_BOT_TOKEN", ""), os.getenv("SLACK_APP_TOKEN", "")
    print("SLACK_BOT_TOKEN:", "있음" if bot.startswith("xoxb-") else "없음 또는 형식 오류 (xoxb-로 시작해야 함)")
    print("SLACK_APP_TOKEN:", "있음" if app_tok.startswith("xapp-") else "없음 또는 형식 오류 (xapp-로 시작해야 함)")
    if not bot.startswith("xoxb-"):
        return 1
    wc = WebClient(token=bot)
    me = wc.auth_test()
    print(f"봇 인증 OK: 워크스페이스 {me['team']}, 봇 사용자 {me['user_id']}")
    chans = wc.conversations_list(types="public_channel", limit=50)["channels"]
    print("채널:", ", ".join(f"#{c['name']}({c['id']}){' 참여' if c.get('is_member') else ''}" for c in chans) or "없음")
    print("SLACK_USER_MAP:", identity._user_map() or "비어 있음 (직원 매핑 필요)")
    print("SLACK_ADMIN_USER_IDS:", identity.admin_slack_ids() or "비어 있음 (승인 요청 DM 받을 관리자 필요)")
    return 0


def main() -> None:
    import sys

    logging.basicConfig(level=logging.INFO)
    if "--check" in sys.argv:
        raise SystemExit(check())
    app = create_app()
    print("Slack 봇 시작 (Socket Mode). Ctrl+C로 종료")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
