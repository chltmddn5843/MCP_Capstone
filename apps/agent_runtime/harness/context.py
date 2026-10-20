"""Harness 4. Context — 토큰 예산을 넘으면 오래된 대화를 잘라낸다. system과 마지막 human 턴은 항상 남긴다."""

from __future__ import annotations

from langchain_core.messages import AnyMessage, trim_messages
from langchain_core.messages.utils import count_tokens_approximately

from apps.agent_runtime.config import CONTEXT_TOKEN_BUDGET


def fit_context(messages: list[AnyMessage]) -> list[AnyMessage]:
    if count_tokens_approximately(messages) <= CONTEXT_TOKEN_BUDGET:
        return messages
    return trim_messages(
        messages,
        max_tokens=CONTEXT_TOKEN_BUDGET,
        token_counter=count_tokens_approximately,
        strategy="last",
        include_system=True,
        start_on="human",
    )
