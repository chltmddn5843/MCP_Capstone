"""Harness 1. Instructions — prompts/*.md를 읽어 역할·프롬프트별 system prompt를 만든다. 코드에 프롬프트를 넣지 않는다."""

from __future__ import annotations

import os
from functools import lru_cache

from apps.agent_runtime.config import PROMPTS_DIR


@lru_cache(maxsize=64)
def _read(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def build_system_prompt(role: str, prompt_name: str | None, prompt_args: dict | None = None) -> str:
    parts = [_read("system_base"), _read(f"role_{role}")]
    if prompt_name:
        tpl = _read(f"prompt_{prompt_name}")
        if tpl:
            try:
                tpl = tpl.format(**(prompt_args or {}))
            except (KeyError, IndexError):
                pass
            parts.append(tpl)
    return "\n\n".join(p for p in parts if p)


def policy_text(name: str) -> str:
    """policy://* Resource의 MVP 대체. 문서 검색 MCP가 붙기 전까지 로컬 md를 쓴다."""
    return _read(f"policy_{name}")
