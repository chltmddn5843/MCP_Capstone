# 개발 규칙 (CONTRIBUTING)

MVP까지 하루, 최종까지 사흘. 규칙은 다섯 개만 지킨다.

## 1. main에 직접 push 금지
main은 보호 브랜치다. 모든 변경은 브랜치 → PR → 머지로만 들어간다.

## 2. 브랜치는 "영역/할일"
```
git switch main && git pull
git switch -c backend/plans-api        # 예: mcp/work-tools, agent/runtime-loop, ui/approval-inbox
```
작업은 **자기 디렉터리 안에서만** 한다. 디렉터리 주인은 아래 표.

| 디렉터리 | 주인 |
| --- | --- |
| `apps/backend`, `db/`, `apps/mock_vendor`, `jobs/` | 백엔드+DB |
| `apps/mcp_work`, `apps/mcp_docs` | MCP |
| `apps/agent_runtime`, `apps/admin_ui`, `apps/slack_bot` | Agent+프론트 |
| `packages/schemas`, `specs/` | **공유. 리드 리뷰 필수** |

## 3. 명세는 `packages/schemas`가 유일한 진실
- 요청·응답 모양, enum, 오류 코드는 전부 `schemas`에서 import한다. 문서나 슬랙 메시지로 합의한 건 명세가 아니다.
- 바꿔야 하면: `schemas` 수정 → `uv run python specs/export.py` → `uv run pytest` → PR에 **"[schema]"** 를 제목에 붙인다. 리드가 승인하면 머지하고, 전체에 알린다.
- 백엔드 스텁(`apps/backend/main.py`)의 라우트 시그니처와 `response_model`은 유지한 채 내부만 바꾼다. `tests/test_contract.py`가 통과해야 머지한다.

## 4. PR은 작게, 하루 한 번 이상
- 한 PR = 한 가지 일. 200줄 넘으면 나눈다.
- 리뷰어 1명 승인 후 **Squash and merge**. 머지한 브랜치는 지운다.
- PR 본문에 "확인 방법" 한 줄 (예: `uv run pytest`, `/docs`에서 `/plans` 호출).

## 5. 비밀값은 절대 커밋하지 않는다
- `.env`는 `.gitignore`에 있다. `.env.example`을 복사해서 쓴다.
- API 키가 커밋되면 즉시 리드에게 말한다. 키 폐기가 먼저, 히스토리 정리는 그다음.

## 충돌이 나면
rebase 하지 말고 리드를 부른다. (`git merge main`으로 해결하고, 안 되면 같이 본다.)

## 처음이라면
1. GitHub Desktop 또는 VS Code의 Source Control 탭을 쓴다. CLI는 몰라도 된다.
2. 첫 PR 연습: `README.md`의 팀원 표에 자기 이름 한 줄 추가 → 브랜치 → 커밋 → PR → 리드 승인 → 머지.
3. 커밋 메시지는 한국어로 한 줄. 예: `조치안 승인 API에 사유 필수 검증 추가`
