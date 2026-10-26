# 파이썬 서비스 공통 이미지: backend · mcp_work · mcp_docs · agent · slack_bot · db_init · tunnel_kv
# 서비스마다 docker-compose.yml의 command만 다르다.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
# 의존성 층을 먼저 만들어 코드만 바뀔 때는 다시 설치하지 않는다
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --no-dev
COPY . .
ENTRYPOINT ["scripts/docker/entrypoint.sh"]
