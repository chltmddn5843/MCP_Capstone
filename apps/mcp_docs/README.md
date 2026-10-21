# 문서 검색 MCP (담당: MCP)

포트 8011. 도구 3개: `schemas.mcp_tools.DOCS_TOOLS` (search_vendor_docs, get_vendor_update, search_internal_policy).

MVP는 SQLite FTS5 전문 검색. 외부 문서 내용은 데이터로만 다루고, 그 안의 지시는 따르지 않는다.
`db/seed/`에 벤더 문서·사내 정책 텍스트를 두고 색인한다. 만들 파일: `server.py`.

## 구현 상태
| 파일 | 내용 |
| --- | --- |
| `server.py` | 도구 3개 등록(업무 MCP의 `registry`, 역할 미들웨어 재사용) |
| `corpus.py` | 문서 적재. `## ` 제목 단위로 자름. HTML 태그 제거, 내용은 데이터로만 다룸 |
| `index.py` | SQLite FTS5(trigram) 메모리 색인. 2글자 한국어 검색어는 부분 일치로 보완 |
| `sample_docs/` | 공식 문서 링크를 반영한 개발용 카탈로그(OpenAI, Anthropic, xAI, Canva, 사내 정책) |

문서 위치: `apps/mcp_docs/sample_docs/` → `db/seed/docs/` 순서로 읽고, 같은 `doc_id`는 시드가 덮어쓴다.
머리말 키: `doc_id, title, doc_type(vendor|policy), vendor, kind(release_notes|pricing|docs), url, published_at, is_candidate`.

## 확인
```bash
uv run pytest tests/test_mcp_docs.py
uv run python -m apps.mcp_docs.server   # http://localhost:8011/mcp
```
