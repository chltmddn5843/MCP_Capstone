"""Harness 8. Observability — trace_id 하나로 Node·도구·토큰·지연을 JSON 로그에 남긴다.
LANGSMITH_TRACING=true 와 LANGSMITH_API_KEY 를 .env에 두면 LangSmith trace도 같은 실행에 붙는다.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

log = logging.getLogger("agent.trace")


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def record(trace_id: str, event: str, **fields) -> None:
    log.info(json.dumps({"trace_id": trace_id, "event": event, "ts": round(time.time(), 3), **fields}, ensure_ascii=False, default=str))


def usage_of(ai_message) -> dict:
    meta = getattr(ai_message, "usage_metadata", None) or {}
    return {"input_tokens": meta.get("input_tokens"), "output_tokens": meta.get("output_tokens")}
