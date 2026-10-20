#!/usr/bin/env bash
# 개발·시연용: 백엔드, 업무 MCP, 문서 MCP, 에이전트, 관리자 화면을 한 번에 띄운다. Ctrl+C로 전부 종료.
# 사용: scripts/run_all.sh            (MCP 모드: 에이전트가 MCP 서버를 거쳐 도구 호출)
#       MCP=0 scripts/run_all.sh      (로컬 모드: 에이전트가 백엔드 REST 직접 호출, MCP 서버 안 띄움)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { cp .env.example .env; echo ".env 생성됨. OPENAI_API_KEY 등을 채우세요 (키 없으면 LLM_MODEL=fake)."; }
mkdir -p db logs
MCP="${MCP:-1}"
pids=()
trap 'echo; echo "종료 중…"; kill "${pids[@]}" 2>/dev/null; wait 2>/dev/null; exit 0' INT TERM

uv run uvicorn apps.backend.main:app --port 8000 >logs/backend.log 2>&1 & pids+=($!)
if [ "$MCP" = "1" ]; then
  uv run python -m apps.mcp_work.server >logs/mcp_work.log 2>&1 & pids+=($!)
  uv run python -m apps.mcp_docs.server >logs/mcp_docs.log 2>&1 & pids+=($!)
  export MCP_WORK_URL="${MCP_WORK_URL:-http://localhost:8010/mcp}" MCP_DOCS_URL="${MCP_DOCS_URL:-http://localhost:8011/mcp}"
else
  export MCP_WORK_URL="" MCP_DOCS_URL=""
fi
for i in $(seq 1 40); do curl -s -o /dev/null localhost:8000/docs && break; sleep 0.5; done
uv run uvicorn apps.agent_runtime.main:app --port 8002 >logs/agent.log 2>&1 & pids+=($!)
for i in $(seq 1 40); do curl -s -o /dev/null localhost:8002/docs && break; sleep 0.5; done

echo "backend  http://localhost:8000/docs"
[ "$MCP" = "1" ] && echo "mcp_work http://localhost:8010/mcp   mcp_docs http://localhost:8011/mcp"
echo "agent    http://localhost:8002/docs   (LLM_MODEL=${LLM_MODEL:-$(grep -E '^LLM_MODEL=' .env | cut -d= -f2-)}, MCP=$MCP)"
echo "admin_ui http://localhost:8501        로그는 logs/*.log"
uv run streamlit run apps/admin_ui/app.py --server.headless true --server.port 8501 2>&1 | grep -v "use_container_width" &
pids+=($!)
wait
