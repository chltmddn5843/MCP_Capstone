"""모델 생성. LLM_MODEL="provider:model" 형식이며, "fake"면 키 없이 도는 스크립트 모델이다."""

from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from apps.agent_runtime.config import LLM_FALLBACK_MODEL, LLM_MODEL


class ScriptedModel(BaseChatModel):
    """키 없이 그래프를 돌리는 스크립트 모델. 시나리오 D-1(이용권)과 프로필 조회만 흉내 낸다."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # noqa: D401
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        humans = [m for m in messages if isinstance(m, HumanMessage)]
        last_idx = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
        tools_done = [m for m in messages[last_idx + 1:] if isinstance(m, ToolMessage)]  # 이번 요청 이후의 도구 결과만
        last_human = str(humans[-1].content) if humans else ""
        names = [m.name for m in tools_done]

        def _cid():
            return f"call_{uuid.uuid4().hex[:8]}"

        def _last_json():
            try:
                return json.loads(tools_done[-1].content)
            except Exception:  # noqa: BLE001
                return {}

        import re

        if not tools_done:
            if "회수" in last_human or "재배정" in last_human:
                call = {"name": "create_action_plan", "args": {"type": "seat_reclaim", "items": [{"employee_id": "emp_sales_02", "contract_id": "ctr_ai_a_2026", "confirmation_id": "cfm_001", "reassign_to_employee_id": "emp_mkt_01"}], "rationale": "휴직 중, 본인 반납 응답 있음", "evidence": [{"source": "confirmations", "ref": "cfm_001", "value": "return_seat"}]}, "id": _cid()}
            elif "실행" in last_human and re.search(r"plan_\w+", last_human):
                call = {"name": "execute_approved_plan", "args": {"plan_id": re.search(r"plan_\w+", last_human).group(0), "idempotency_key": f"idem_{uuid.uuid4().hex[:8]}"}, "id": _cid()}
            elif "이용권" in last_human or "좌석" in last_human:
                call = {"name": "create_action_plan", "args": {"type": "seat_assign", "items": [{"employee_id": "emp_mkt_01", "contract_id": "ctr_ai_a_2026"}], "rationale": "미배정 이용권이 있어 신청자에게 배정", "evidence": [{"source": "inventory", "ref": "ctr_ai_a_2026", "value": {"unassigned": 2}}]}, "id": _cid()}
            else:
                call = {"name": "get_my_profile", "args": {}, "id": _cid()}
            msg = AIMessage(content="", tool_calls=[call])
        else:
            last = tools_done[-1].content[:300]
            status = _last_json().get("status")
            summary = {"executed": "조치가 즉시 실행됐습니다.", "pending_approval": "조치안을 만들었고 담당자 승인을 기다립니다.", "approved": "승인된 조치안입니다."}.get(status, "요청을 처리했습니다.")
            msg = AIMessage(content=f"(스크립트 모델) {summary} 마지막 단계 {names[-1]} 결과 근거: {last}")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def make_model(name: str) -> BaseChatModel:
    if name == "fake":
        return ScriptedModel()
    from langchain.chat_models import init_chat_model

    return init_chat_model(name)


def get_models() -> tuple[BaseChatModel, BaseChatModel | None]:
    primary = make_model(LLM_MODEL)
    fallback = make_model(LLM_FALLBACK_MODEL) if LLM_FALLBACK_MODEL else None
    return primary, fallback
