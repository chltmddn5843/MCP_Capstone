"""에이전트 런타임 설정. 전부 환경변수로 바꿀 수 있고, 값은 AGENT_DESIGN.md의 Harness 표와 같다."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MCP_WORK_URL = os.getenv("MCP_WORK_URL", "")  # 비어 있으면 로컬 REST 모드
MCP_DOCS_URL = os.getenv("MCP_DOCS_URL", "")

LLM_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.4-mini")  # "공급사:API 모델명". openai:gpt-5.4-nano, xai:grok-4.7, fake
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")  # 예: openai:gpt-5.4-nano
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# Agent Loop 한도
MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "8"))
MAX_SECONDS = int(os.getenv("AGENT_MAX_SECONDS", "120"))
MAX_SAME_TOOL = int(os.getenv("AGENT_MAX_SAME_TOOL", "3"))

# Context
CONTEXT_TOKEN_BUDGET = int(os.getenv("AGENT_CONTEXT_TOKENS", "24000"))
TOOL_RESULT_MAX_CHARS = int(os.getenv("AGENT_TOOL_RESULT_MAX_CHARS", "4000"))

# State: 백엔드와 같은 PostgreSQL, 스키마 agent (checkpoint 테이블 + tasks). docs/아키텍처.md 6절
AGENT_DB_URL = os.getenv("DATABASE_URL", "postgresql://capstone:capstone@localhost:5432/capstone").replace("+psycopg", "", 1)
AGENT_DB_URL += ("&" if "?" in AGENT_DB_URL else "?") + "options=-csearch_path%3Dagent"

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
