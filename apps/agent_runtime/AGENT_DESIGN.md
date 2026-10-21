# AI Agent 설계 (State · Graph · Harness)

평가 항목 "AI Agent 설계·구현"과 "Harness"에 대응하는 설계다. 코드는 `graph.py`, `state.py`, `harness/`에 있고, 이 문서의 표와 1:1로 맞춘다.

## 1. 에이전트가 하는 일

역할(직원·HRD·자산관리·승인자·시스템)에 따라 다른 시스템 프롬프트와 도구 집합을 받고, 질문에 대해 도구를 골라 부르며 근거와 함께 답한다. 데이터를 바꾸는 일은 조치안(plan)으로만 만들고, 실행 도구 앞에서는 멈춰 사람의 승인을 기다린다.

## 2. State

| 필드 | 타입 | 뜻 | 누가 바꾸나 |
| --- | --- | --- | --- |
| `messages` | list[Message] (add_messages) | 대화 전체. thread_id 단위로 checkpointer에 남는다 | call_model, tools, approval_gate |
| `task_id` | str | 현재 작업. 실행 문맥(모델·도구)을 찾는 키 | 입력 |
| `requester_id`, `requester_role` | str | 요청자. 역할이 도구 노출과 프롬프트를 가른다 | 입력 |
| `prompt_name` | str? | MCP Prompt 이름 (review_update 등) | 입력 |
| `turn` | int | 모델 호출 횟수 | call_model |
| `tool_counts` | dict[str,int] | 도구별 호출 횟수 | tools |
| `evidence` | list[Evidence] | 도구 결과에서 모은 근거 (source, ref, value) | tools |
| `plan_id` | str? | create_action_plan 결과 | tools |
| `pending_approval` / `approval_decision` | dict? | 승인 카드와 결정 | approval_gate |
| `answer` | str? | 최종 답 | finalize |
| `started_at` | float | 작업 시작 시각 (시간 한도용) | prepare |
| `stop_reason` | str? | answer · turn_limit · time_limit · tool_repeat · rejected | check_limits, approval_gate, finalize |

## 3. Graph

```mermaid
flowchart TD
    START --> prepare
    prepare --> call_model
    call_model --> check_limits
    check_limits -->|tool_calls 없음 또는 한도 초과| finalize
    check_limits -->|조회 도구| tools
    check_limits -->|변경 도구 (destructiveHint)| approval_gate
    approval_gate -->|interrupt → 승인| tools
    approval_gate -->|거절 → ToolMessage(rejected)| call_model
    tools --> call_model
    finalize --> END
```

| Node | 하는 일 | 분기 |
| --- | --- | --- |
| `prepare` | 작업 단위 카운터 초기화. 대화는 thread에 이어진다 | – |
| `call_model` | Context를 예산에 맞추고, 재시도·대체 모델로 감싼 모델 호출 | – |
| `check_limits` | 턴·시간·같은 도구 반복 한도 검사 | 한도 초과 → finalize |
| `approval_gate` | 변경 도구 앞에서 `interrupt(승인 카드)`. 상태는 checkpointer에 저장되고 `POST /ai/tasks/{id}/approval`로 재개 | 승인 → tools, 거절 → call_model |
| `tools` | 도구 실행, 결과 길이 제한·PII 마스킹, 오류는 ToolMessage로, 근거 수집, TOOL_START/END 이벤트 | – (반복: → call_model) |
| `finalize` | 마지막 AI 메시지에서 답을 뽑고, 한도 종료면 그 사실을 덧붙인다 | → END |

반복은 `call_model → check_limits → tools → call_model` 고리다. 모델이 도구를 더 부르지 않거나 한도에 닿으면 끝난다.

### Agentic AI 요소
- **도구 선택**: 모델이 역할별 도구 목록에서 고른다. 서버가 역할에 맞지 않는 도구를 숨기므로 권한 밖 호출은 아예 보이지 않는다.
- **근거 기반 답변**: 모든 도구 결과가 `evidence`에 쌓이고, 답 끝에 "근거:" 줄로 인용한다.
- **승인 게이트(HITL)**: 변경 도구는 실행 전에 멈추고, 승인자가 결정해야 이어진다. 에이전트는 실행 내용을 바꾸지 못하고 plan_id만 넘긴다.
- **상태 저장·재개**: thread_id 단위 checkpointer(SQLite). 승인 대기 중 서버가 살아 있으면 그대로 재개하고, 같은 thread_id로 대화를 이어갈 수 있다.
- **역할 프로필**: Instructions(`prompts/role_*.md`)와 도구 집합이 역할마다 다르다.

## 4. Harness 8요소 매핑

| 구성요소 | 위치 | 적용 기준 (강의 표 6-3) |
| --- | --- | --- |
| Instructions | `harness/instructions.py`, `prompts/*.md` | 역할·규칙·금지·출력형식을 md로 버전 관리. 코드에 프롬프트 없음 |
| Tools | `harness/tools.py` | MCP Client(FastMCP Client, Streamable HTTP) 또는 로컬 REST. 결과 4,000자 제한, 오류는 ToolMessage |
| Agent Loop | `graph.py` `check_limits` | 최대 8턴, 120초, 같은 도구 3회 |
| Context | `harness/context.py` | 토큰 예산 24k. 넘으면 오래된 대화를 자른다 (system·마지막 human 유지) |
| State·Memory | `AsyncSqliteSaver`, `tasks.TaskStore` | thread_id 단위 저장, 승인 대기 후 그대로 재개, 작업 이력 SQLite |
| Guardrails | `harness/guardrails.py`, `approval_gate` | destructiveHint 도구는 interrupt. 도구 결과의 이메일·전화번호 마스킹 |
| Recovery | `harness/recovery.py` | 429·503 등 일시 오류 2회 재시도, 계속 실패하면 LLM_FALLBACK_MODEL, 그래도 실패면 FAILED |
| Observability | `harness/observability.py` | trace_id 하나로 Node·도구·토큰·지연 JSON 로그. LANGSMITH_TRACING=true면 LangSmith trace |

값은 `config.py`에서 환경변수로 바꿀 수 있다.

## 5. 진행 이벤트와 API

| 이벤트 | 언제 | 화면 |
| --- | --- | --- |
| TOKEN | 답변 생성 중 | 답변 영역에 이어 붙임 |
| TOOL_START · TOOL_END | 도구 실행 전후 | "이용권 현황 조회 중…" 상태 표시 |
| APPROVAL_REQUIRED | 변경 도구 앞에서 멈췄을 때 | 승인 카드 (도구·인자·plan_id·근거) |
| DONE · FAILED | 작업 종료 | 스트림 닫고 작업 목록 갱신 |

API는 `schemas/agent.py` 머리말과 같다. SSE는 `?after=<seq>`로 이어 받을 수 있어 승인 뒤 재구독이 가능하다.

## 6. 실행 모드

| 설정 | 뜻 |
| --- | --- |
| `LLM_MODEL=anthropic:claude-opus-4-7` | 기본. `openai:gpt-5.2` 또는 `xai:grok-4.7`로 바꿀 수 있다 |
| `LLM_MODEL=fake` | 키 없이 그래프를 돌리는 스크립트 모델 (테스트·배선 확인용) |
| `MCP_WORK_URL` 비어 있음 | 로컬 모드: 백엔드 REST 직접 호출. 도구 이름·입출력은 MCP와 같다 |
| `MCP_WORK_URL=http://localhost:8010/mcp` | MCP 모드: tools/list를 받아 쓴다 (최종 목표) |

## 7. v2 변경 예정 (설계 확정, 구현 전)

`docs/설계문서.md` 12절. 현재 그래프 앞에 `classify_intent` → (`collect_conditions` → `ask_user`) 분기를 붙이고, State에 `intent`, `conditions`를 더한다. 역할은 employee·admin·system. 배치가 조건 충족 시 시스템 계정으로 작업을 만드는 호출 경로를 추가한다. 기존 노드·Harness 매핑은 바뀌지 않는다.
