"""Harness 6. Guardrails — 변경 도구 앞에서 멈추고(interrupt), 도구 결과의 개인정보를 마스킹한다."""

from __future__ import annotations

import re

from schemas.mcp_tools import TOOLS

DESTRUCTIVE_TOOLS: frozenset[str] = frozenset(t.name for t in TOOLS if t.destructive)
WRITE_TOOLS: frozenset[str] = frozenset(t.name for t in TOOLS if not t.read_only)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")


def is_destructive(tool_name: str) -> bool:
    return tool_name in DESTRUCTIVE_TOOLS


def mask_pii(text: str) -> str:
    text = _EMAIL.sub(lambda m: m.group(0)[:2] + "***@" + m.group(0).split("@")[1], text)
    text = _PHONE.sub("010-****-****", text)
    return text


_ID = re.compile(r"\b(?:plan|emp|task|cfm|ctr|prj|upd|sug|mdl|tool|need|anm|ev|sav|aud|th|idem|dept|src)_[A-Za-z0-9_]+\b")
_TOOL_NAMES = re.compile(r"\b(" + "|".join(sorted((t.name for t in TOOLS), key=len, reverse=True)) + r")\b")
_EVIDENCE_LINE = re.compile(r"\**\s*(근거|참고한 데이터|참고 데이터)\s*\**\s*[:：].*$", re.S)  # 어디에 있든 '근거:' 부터 끝까지
_CODE = re.compile(r"`([^`]*)`")
_ERRCODE = re.compile(r"\b(forbidden|not_found|invalid|conflict|stale|unauthorized|internal|tool_error)\b")


def public_channel(role: str | None, channel: str | None) -> bool:
    """직원이거나 Slack 채널이면 '공개 답변' (자연어만, 내부 식별자·도구 이름·근거 줄 없음)."""
    return role == "employee" or channel == "slack"


def sanitize_public_answer(text: str) -> str:
    """모델이 규칙을 어겨도 내부 정보가 새지 않게 하는 마지막 안전장치. 참고 데이터는 result.evidence에 그대로 남는다."""
    if not text:
        return text
    text = _EVIDENCE_LINE.sub("", text)  # 마지막 '근거:' 블록 제거
    text = _CODE.sub(r"\1", text)
    text = _TOOL_NAMES.sub("", text)
    text = _ID.sub("", text)
    text = _ERRCODE.sub("", text)
    text = re.sub(r"\(\s*[,、·/\s]*\)", "", text)  # 식별자만 들어 있던 괄호
    text = re.sub(r"\bstatus\s*=\s*\w+", "", text)
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def approval_summary(tool_name: str, tool_input: dict) -> str:
    if tool_name == "execute_approved_plan":
        return f"승인된 조치안 {tool_input.get('plan_id')} 을(를) 실행합니다. 벤더(Mock) API가 호출되고 결과가 기록됩니다."
    return f"변경 도구 {tool_name} 을(를) 실행합니다."
