"""Harness 7. Recovery — 429·503 같은 일시 오류는 2회 재시도하고, 계속 실패하면 대체 모델을 쓴다."""

from __future__ import annotations

import asyncio
import logging

from langchain_core.language_models import BaseChatModel

from apps.agent_runtime.config import LLM_FALLBACK_MODEL, LLM_MAX_RETRIES

log = logging.getLogger("agent.recovery")
RETRYABLE_MARKERS = ("429", "503", "502", "529", "overloaded", "rate limit", "timeout", "connection")


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in (408, 409, 429, 500, 502, 503, 529):
        return True
    return any(m in str(exc).lower() for m in RETRYABLE_MARKERS)


async def call_with_recovery(model: BaseChatModel, fallback: BaseChatModel | None, messages, *, trace_id: str):
    """model.ainvoke를 재시도·대체 모델로 감싼다. 반환: (AIMessage, used_fallback: bool)"""
    last: Exception | None = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            return await model.ainvoke(messages), False
        except Exception as exc:  # noqa: BLE001
            last = exc
            if not _retryable(exc):
                raise
            delay = 1.5 * (attempt + 1)
            log.warning("trace=%s llm retry %d/%d after %.1fs: %s", trace_id, attempt + 1, LLM_MAX_RETRIES, delay, exc)
            await asyncio.sleep(delay)
    if fallback is not None:
        log.warning("trace=%s switching to fallback model %s", trace_id, LLM_FALLBACK_MODEL)
        return await fallback.ainvoke(messages), True
    raise last  # type: ignore[misc]
