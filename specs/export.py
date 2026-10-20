"""schemas 패키지에서 명세 파일을 내보낸다. PR 전에 실행해 diff를 같이 올린다.
    uv run python specs/export.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 저장소 루트

from apps.backend.main import app as backend_app
from apps.agent_runtime.main import app as agent_app
from schemas.mcp_tools import DOCS_TOOLS, PROMPTS, RESOURCES, WORK_TOOLS, tool_json_schema

OUT = Path(__file__).parent


def main() -> None:
    (OUT / "openapi.backend.json").write_text(json.dumps(backend_app.openapi(), ensure_ascii=False, indent=2))
    (OUT / "openapi.agent.json").write_text(json.dumps(agent_app.openapi(), ensure_ascii=False, indent=2))
    mcp = {
        "work_mcp": {"tools": [tool_json_schema(t) for t in WORK_TOOLS]},
        "docs_mcp": {"tools": [tool_json_schema(t) for t in DOCS_TOOLS]},
        "resources": RESOURCES,
        "prompts": PROMPTS,
    }
    (OUT / "mcp_tools.json").write_text(json.dumps(mcp, ensure_ascii=False, indent=2))
    print("wrote specs/openapi.backend.json, specs/openapi.agent.json, specs/mcp_tools.json")


if __name__ == "__main__":
    main()
