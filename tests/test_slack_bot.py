"""Slack 봇: 실제 Slack 없이 메시지 빌더, 진행 갱신, 승인 흐름, 버튼 처리를 가짜 Slack 클라이언트로 확인한다."""

from __future__ import annotations

import os

os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test")

from apps.slack_bot import app as bot  # noqa: E402
from apps.slack_bot import client as api  # noqa: E402
from apps.slack_bot import identity, send  # noqa: E402


class FakeSlack:
    def __init__(self):
        self.posted, self.updated, self.ephemeral, self.opened = [], [], [], []

    def chat_postMessage(self, **kw):
        self.posted.append(kw)
        return {"ts": f"ts{len(self.posted)}", "thread_ts": kw.get("thread_ts")}

    def chat_update(self, **kw):
        self.updated.append(kw)
        return {"ok": True}

    def chat_postEphemeral(self, **kw):
        self.ephemeral.append(kw)

    def conversations_open(self, users):
        self.opened.append(users)
        return {"channel": {"id": f"D_{users}"}}


def ev(type_, seq, **f):
    return {"type": type_, "task_id": "task_1", "seq": seq, "at": "2026-10-21T09:00:00Z", **f}


def test_builders_have_buttons_and_links():
    b = send.build_suggestion({"id": "sug_1", "body": "문서 비교 기능을 설문 비교에 쓸 수 있어요"}, "교육 과정별 설문 결과 비교", {"vendor": "AI-A", "url": "https://v.example/rn", "affected_plans": ["Enterprise"]})
    assert b[-1]["type"] == "actions" and [e["action_id"] for e in b[-1]["elements"]] == ["fb_useful", "fb_irrelevant", "fb_question"]
    assert "원문 보기" in b[2]["elements"][0]["text"]
    c = send.build_confirmation({"id": "cfm_1"}, "AI-A Enterprise Chat", None)
    assert "응답이 없어도 회수되지 않습니다" in c[0]["text"]["text"]
    a = send.build_approval_request({"task_id": "task_1", "input": "회수해줘", "requester_id": "emp_asset_01", "approval": {"summary": "승인된 조치안 plan_9 을(를) 실행합니다.", "evidence": [{"source": "confirmations", "ref": "cfm_001"}]}})
    assert [e["action_id"] for e in a[-1]["elements"]] == ["ap_yes", "ap_no"]
    assert send.build_answer({"answer": "추천: b-mid", "evidence": [{"source": "get_eval_results", "ref": "customer_inquiry_classification"}]})[1]["type"] == "context"


def test_follow_updates_one_message_then_answers(monkeypatch):
    slack = FakeSlack()
    events = [ev("TOOL_START", 1, tool_call={"id": "c1", "name": "get_my_profile", "input": {}}),
              ev("TOOL_END", 2, tool_call={"id": "c1", "name": "get_my_profile", "input": {}, "output": "{}", "error": None}),
              ev("TOKEN", 3, text="등록 업무는"), ev("DONE", 4, result={"answer": "등록 업무는 2개입니다.", "evidence": [{"source": "get_my_profile", "ref": "emp_mkt_01"}]})]
    monkeypatch.setattr(api, "stream_events", lambda token, task_id, after=0, timeout=180: iter(events))
    bot._follow(slack, "dev.emp_mkt_01", "task_1", "D1", "ts1", None, 0)
    final = slack.updated[-1]
    assert final["text"] == "완료" and final["blocks"][0]["text"]["text"].startswith("등록 업무는 2개")
    assert all(u["ts"] == "ts1" for u in slack.updated)  # 같은 메시지만 갱신


def test_follow_approval_notifies_admin_and_resumes_after_decision(monkeypatch):
    slack = FakeSlack()
    monkeypatch.setenv("SLACK_ADMIN_USER_IDS", "U_ADMIN")
    first = [ev("APPROVAL_REQUIRED", 1, approval={"tool_name": "execute_approved_plan", "tool_input": {"plan_id": "plan_9"}, "plan_id": "plan_9", "summary": "승인된 조치안 plan_9 을(를) 실행합니다.", "evidence": []})]
    monkeypatch.setattr(api, "stream_events", lambda token, task_id, after=0, timeout=180: iter(first))
    monkeypatch.setattr(api, "agent", lambda m, p, t, **kw: {"task_id": "task_1", "input": "plan_9 실행해줘", "requester_id": "emp_asset_01",
                                                               "approval": first[0]["approval"]})
    bot._follow(slack, "dev.emp_asset_01", "task_1", "D1", "ts1", None, 0)
    assert "관리자 확인" in slack.updated[-1]["text"] and slack.opened == ["U_ADMIN"]
    assert slack.posted[-1]["channel"] == "D_U_ADMIN" and bot.PENDING["task_1"]["after"] == 1
    # 관리자가 버튼으로 확인 → 승인 API 호출 → 요청자 메시지 이어서 갱신
    approved = {}
    monkeypatch.setattr(identity, "resolve", lambda uid: ("dev.emp_asset_01", {"id": "emp_asset_01", "role": "admin"}))
    monkeypatch.setattr(api, "approve_task", lambda token, task_id, ok, reason: approved.update(task_id=task_id, ok=ok))
    second = [ev("TOOL_START", 2, tool_call={"id": "c2", "name": "execute_approved_plan", "input": {}}),
              ev("TOOL_END", 3, tool_call={"id": "c2", "name": "execute_approved_plan", "input": {}, "output": "{}", "error": None}),
              ev("DONE", 4, result={"answer": "처리했습니다.", "evidence": []})]
    monkeypatch.setattr(api, "stream_events", lambda token, task_id, after=0, timeout=180: iter(second) if after == 1 else iter([]))
    body = {"user": {"id": "U_ADMIN"}, "channel": {"id": "D_U_ADMIN"}, "message": {"ts": "ts9"}}
    bot.on_approval(ack=lambda: None, body=body, action={"action_id": "ap_yes", "value": "task_1"}, client=slack)
    import time
    time.sleep(0.3)  # 백그라운드 스레드 완료 대기
    assert approved == {"task_id": "task_1", "ok": True}
    assert slack.updated[-1]["text"] == "완료" and "task_1" not in bot.PENDING


def test_feedback_button_calls_backend(monkeypatch):
    slack = FakeSlack()
    calls = {}
    monkeypatch.setattr(identity, "resolve", lambda uid: ("dev.emp_mkt_01", {"id": "emp_mkt_01", "role": "employee"}))
    monkeypatch.setattr(api, "feedback", lambda token, sid, reaction: calls.update(sid=sid, reaction=reaction))
    bot.on_feedback(ack=lambda: None, body={"user": {"id": "U1"}, "channel": {"id": "C1"}}, action={"action_id": "fb_irrelevant", "value": "sug_1"}, client=slack)
    assert calls == {"sid": "sug_1", "reaction": "irrelevant"} and "관련 없음" in slack.ephemeral[-1]["text"]


def test_identity_falls_back_to_user_map(monkeypatch):
    identity._cache.clear()
    monkeypatch.setenv("SLACK_USER_MAP", '{"U_MKT01": "emp_mkt_01"}')
    monkeypatch.setattr(identity, "backend", lambda *a, **k: (_ for _ in ()).throw(api.ApiError("not_found", "no route")))
    monkeypatch.setattr(identity, "_dev_login", lambda emp_id: (f"dev.{emp_id}", {"id": emp_id, "role": "employee"}))
    token, emp = identity.resolve("U_MKT01")
    assert token == "dev.emp_mkt_01" and emp["id"] == "emp_mkt_01"
    try:
        identity.resolve("U_UNKNOWN")
        raise AssertionError("매핑 없는 사용자는 실패해야 함")
    except api.ApiError as exc:
        assert exc.code == "not_found"


def test_create_app_registers_listeners_without_network():
    app = bot.create_app(verify_token=False)
    assert len(app._listeners) >= 10  # 이벤트 2 + 버튼 8
