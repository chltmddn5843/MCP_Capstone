# DB (담당: 백엔드+DB)

PostgreSQL 16, 스키마 `app`(업무)·`agent`(LangGraph, 라이브러리가 생성). 설계 근거는 `docs/아키텍처.md` 6절.

| 파일 | 내용 |
| --- | --- |
| `schema.dbml` | 테이블 24개 ERD 원본. [dbdiagram.io](https://dbdiagram.io/d)에 붙여 넣으면 그림으로 본다 |
| `migrations/` | Alembic (다음 PR). `schema.dbml`과 같이 고친다 |
| `seed/` | 10절 '한빛제조' 시드. `apps/backend/fixtures.py`의 id를 반드시 포함 (계약 테스트) |

## 로컬 DB 띄우기

```bash
db/reset.sh        # postgres 컨테이너 기동 → schema.sql 적용 → seed.py 더미 적재 → 테이블별 행 수 출력
```

DBeaver 접속: PostgreSQL · Host `localhost` · Port `5432` · DB `capstone` · User `capstone` · Password `capstone`(개발용, `.env`로 변경 가능) → 스키마 `app`.
`reset.sh`는 매번 `app` 스키마를 지우고 다시 만든다. `uv run pytest`도 이 DB를 쓴다(`tests/conftest.py`가 테스트마다 스키마·시드를 다시 넣는다). postgres가 떠 있어야 한다. 더미는 `random.seed(7)`라 매번 같다.

규칙: id는 문자열(`emp_…`), enum 값은 `schemas.common`의 영어 값, 시각은 `timestamptz`(UTC), 금액은 원화 `int` + 달러 `numeric`.

## 스키마 점검 결과 (2026-10-21)

`packages/schemas/schemas/entities.py`(응답 모양)와 설계문서 v2 6절, 아키텍처 v3를 대조했다.

### A. 설계에 있는데 공유 스키마에 없는 것 → `[schema]` PR 필요 (리드 리뷰)

| 항목 | 설계 근거 | 영향 |
| --- | --- | --- |
| `Tool.kind` (ai·software) | v2 6절, Adobe 시나리오 E | 카탈로그에서 AI/일반 SW 구분 불가 |
| `Department.slack_channel_id`, `suggestions_enabled` | v2 6절, 알림 정책 | F1 자동 발송·팀별 스위치 불가 |
| `ActionPlan.ai_opinion` | v2 6절, D-1 | 승인 대기 AI 의견을 화면에 못 보냄 |
| `ReviewRun` 모델 + `GET /review-runs` | v2 6·8절 | 자동 제안 판단 기록 화면 불가 |
| `LoginRequest`/`TokenResponse`, `JobRun` | 아키텍처 v3 5-2·5-5 | JWT 로그인, 실패 작업 화면 |

### B. DB에만 두는 것 (API 응답 변경 없음)

| 테이블·컬럼 | 이유 |
| --- | --- |
| `employees.password_hash` | 로그인 검증용. 응답에 절대 넣지 않는다 |
| `usage_records`, `api_keys` | `UsageSummary`·`BreakdownRow`는 이 테이블을 집계한 결과. 대화 내용은 저장하지 않는다 |
| `suggestion_holds` | "관련 없음 2회 → 4주 보류" 규칙 상태 |
| `job_runs` | 큐 작업 상태·재시도·DLQ |
| `action_plans.execution_key` | 지금 메모리(`fixtures.EXECUTIONS`)에 있는 멱등키를 DB로 |
| `suggestions.target_employee_id`·`target_dept_id` | API의 다형 `target_id`를 FK 두 개로 나눠 무결성 확보. 응답에서 다시 `target_id`로 합친다 |
| `models.tool_id` (선택) | 모델이 어느 API 제품 소속인지. 지금은 `vendor` 문자열뿐 |

### C. 파생값이라 저장하지 않는 것

`Employee.dept_name`(JOIN), `Anomaly.scope_name`(JOIN), `ToolWithPlan.contract`(JOIN), `ContractInventory`(seat_assignments 집계).

### D. 무결성 규칙 (DDL로 강제)

| 규칙 | 구현 |
| --- | --- |
| 한 직원은 한 계약에 좌석 하나 | `seat_assignments` 부분 UNIQUE `(contract_id, employee_id) WHERE status='assigned'` |
| 같은 사용량 두 번 적재 금지 | `usage_records.vendor_record_id` UNIQUE |
| 같은 릴리스 노트 두 번 수집 금지 | `vendor_updates.url` UNIQUE |
| 처리 요청 중복 실행 금지 | `action_plans.execution_key`, `job_runs.idempotency_key` UNIQUE |
| 한 사람 한 제안에 반응 하나 | `feedback (suggestion_id, employee_id)` UNIQUE |
| 사용 의사 확인 중복 금지 | `confirmations (plan_id, employee_id)` UNIQUE |
| 감사 로그 변경 금지 | 앱 DB 계정에 `audit_log` UPDATE·DELETE 권한 없음 |
| 승인 뒤 상태 재확인 | `UPDATE action_plans … WHERE status = :expected` (0행이면 `stale` 409) |

### E. 남은 질문

- `anomalies.scope_*`는 대상이 4종이라 다형 참조로 둔다(FK 없음). 괜찮은지.
- `registered_tasks.tools_used`를 배열로 둘지 연결 테이블로 뺄지. 배열이면 FK 검사는 앱에서.
- 시드 규모(직원 180, 사용량 60일)를 MVP에서 다 채울지, 시연 시나리오 행만 채울지.
