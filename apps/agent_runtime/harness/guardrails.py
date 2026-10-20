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


def approval_summary(tool_name: str, tool_input: dict) -> str:
    if tool_name == "execute_approved_plan":
        return f"승인된 조치안 {tool_input.get('plan_id')} 을(를) 실행합니다. 벤더(Mock) API가 호출되고 결과가 기록됩니다."
    return f"변경 도구 {tool_name} 을(를) 실행합니다."
