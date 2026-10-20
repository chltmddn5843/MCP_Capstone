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
        tools_done = [m for m in messages if isinstance(m, ToolMessage)]
        last_human = humans[-1].content if humans else ""
        wants_seat = "이용권" in str(last_human) or "좌석" in str(last_human)
        names = [m.name for m in tools_done]
        if not tools_done:
            if wants_seat:
                call = {"name": "create_action_plan", "args": {"type": "seat_assign", "items": [{"employee_id": "emp_mkt_01", "contract_id": "ctr_ai_a_2026"}], "rationale": "미배정 이용권이 있어 신청자에게 배정", "evidence": [{"source": "inventory", "ref": "ctr_ai_a_2026", "value": {"unassigned": 2}}]}, "id": f"call_{uuid.uuid4().hex[:8]}"}
            else:
                call = {"name": "get_my_profile", "args": {}, "id": f"call_{uuid.uuid4().hex[:8]}"}
            msg = AIMessage(content="", tool_calls=[call])
        elif names[-1] == "create_action_plan":
            try:
                plan_id = json.loads(tools_done[-1].content).get("plan_id", "plan_001")
            except Exception:  # noqa: BLE001
                plan_id = "plan_001"
            msg = AIMessage(content="", tool_calls=[{"name": "execute_approved_plan", "args": {"plan_id": plan_id, "idempotency_key": f"idem_{uuid.uuid4().hex[:8]}"}, "id": f"call_{uuid.uuid4().hex[:8]}"}])
        else:
            last = tools_done[-1].content[:300]
            msg = AIMessage(content=f"(스크립트 모델) 요청을 처리했습니다. 마지막 도구 {names[-1]} 결과 근거: {last}")
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
