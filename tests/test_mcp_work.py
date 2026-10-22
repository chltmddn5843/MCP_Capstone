"""업무 MCP 테스트: 명세 등록, 역할별 노출, 백엔드 오류 봉투 전달, 기능별 흐름, Resource·Prompt."""

import pytest
from mcp.shared.exceptions import MCPError
from schemas.common import Role
from schemas.mcp_tools import PROMPTS, RESOURCES, WORK_TOOLS, tools_for_role

from apps.mcp_work.server import mcp
from tests.mcp_helpers import backend_post, connect, error_of

pytestmark = pytest.mark.anyio   # anyio pytest 플러그인 (추가 의존성 없음)

PERIOD = {"start": "2026-10-07", "end": "2026-10-20"}
WORK = {t.name for t in WORK_TOOLS}


# ---------- 명세대로 등록 ----------

async def test_every_spec_registered_with_its_schemas(monkeypatch):
    async with connect(mcp, monkeypatch, "system") as c:
        tools = {t.name: t for t in await c.list_tools()}
    specs = {s.name: s for s in WORK_TOOLS if Role.system in s.roles}
    assert set(tools) == set(specs)
    for name, spec in specs.items():
        # FastMCP는 스키마의 $ref를 펼쳐서 내보내므로 필드 구성과 필수 여부를 비교한다
        for published, model in ((tools[name].input_schema, spec.input_model),
                                 (tools[name].output_schema, spec.output_model)):
            expected = model.model_json_schema()
            assert set(published.get("properties", {})) == set(expected.get("properties", {})), name
            assert published.get("required") == expected.get("required"), name
        assert bool(tools[name].annotations.destructive_hint) == spec.destructive, name
        assert tools[name].meta["roles"] == [r.value for r in spec.roles]


@pytest.mark.parametrize("who, role", [("employee", Role.employee), ("admin", Role.admin), ("system", Role.system)])
async def test_tools_list_follows_role(monkeypatch, who, role):
    async with connect(mcp, monkeypatch, who) as c:
        visible = {t.name for t in await c.list_tools()}
    assert visible == {t.name for t in tools_for_role(role)} & WORK


async def test_no_token_sees_nothing_and_cannot_call(monkeypatch):
    async with connect(mcp, monkeypatch, None) as c:
        assert await c.list_tools() == []
        result = await c.call_tool("get_my_profile", {}, raise_on_error=False)
    assert error_of(result)["code"] == "unauthorized"


async def test_hidden_tool_call_is_forbidden(monkeypatch):
    async with connect(mcp, monkeypatch, "employee") as c:
        result = await c.call_tool("execute_approved_plan", {"plan_id": "plan_001", "idempotency_key": "k"},
                                   raise_on_error=False)
    err = error_of(result)
    assert err["code"] == "forbidden" and "system" in err["details"]["allowed_roles"]


# ---------- 오류 처리 ----------

async def test_backend_error_envelope_is_passed_through(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        result = await c.call_tool("get_plan_status", {"plan_id": "plan_nope"}, raise_on_error=False)
    assert error_of(result) == {"code": "not_found", "message": "조치안 없음", "details": None}


async def test_input_validation_error(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        result = await c.call_tool("get_usage_breakdown", {"project_id": "p", "period": PERIOD, "by": "weekday"},
                                   raise_on_error=False)
    assert result.is_error


async def test_request_confirmation_creates_with_due_date(monkeypatch):
    # POST /confirmations 라우트가 백엔드에 추가됨 (명세 ROUTES, 응답 기한 5영업일)
    async with connect(mcp, monkeypatch, "asset") as c:
        out = (await c.call_tool("request_confirmation", {"employee_id": "emp_sales_02", "plan_id": "plan_002",
                                                          "question": "계속 쓰시나요?"})).structured_content
    assert out["confirmation_id"].startswith("cfm_") and out["due_at"]


# ---------- F1 업데이트 → 직원 업무 ----------

async def test_f1_relevant_tasks_and_suggestion(monkeypatch):
    async with connect(mcp, monkeypatch, "system") as c:
        found = (await c.call_tool("find_relevant_tasks", {"update_id": "upd_chatgpt_doc_compare"})).structured_content
        assert found["update"]["affected_plans"] == ["Enterprise"]
        assert all(cand["employee_id"] for cand in found["candidates"])
        blank = await c.call_tool("save_suggestion", {"update_id": "upd_chatgpt_doc_compare", "target_type": "employee",
                                                      "target_id": "emp_hrd_01", "relevance": " ", "body": "x"},
                                  raise_on_error=False)
        assert error_of(blank)["code"] == "invalid"
        saved = (await c.call_tool("save_suggestion", {
            "update_id": "upd_chatgpt_doc_compare", "target_type": "employee", "target_id": "emp_hrd_01",
            "task_id": "task_hrd_survey", "relevance": "등록 업무가 여러 설문 파일 비교를 필요로 함",
            "body": "등록하신 '교육 과정별 설문 결과 비교' 업무에 쓸 수 있는 기능이 추가됐어요."})).structured_content
    assert saved["status"] == "draft"


async def test_f1_admin_sees_team_level_only(monkeypatch):
    async with connect(mcp, monkeypatch, "admin") as c:
        found = (await c.call_tool("find_relevant_tasks", {"update_id": "upd_chatgpt_doc_compare"})).structured_content
        adoption = (await c.call_tool("get_team_adoption", {"period": PERIOD})).structured_content
    assert all(cand["employee_id"] is None for cand in found["candidates"])
    assert {t["team_id"] for t in adoption["teams"]} == {"dept_mkt", "dept_cs", "dept_md"}  # 제안 반응이 있는 팀만


async def test_profile_and_task_upsert(monkeypatch):
    async with connect(mcp, monkeypatch, "employee") as c:
        created = (await c.call_tool("upsert_my_task", {"title": "보도자료 비교", "description": "경쟁사 보도자료 3건 비교",
                                                        "frequency": "weekly"})).structured_content
        await c.call_tool("upsert_my_task", {"task_id": created["task_id"], "title": "보도자료 비교(수정)",
                                             "description": "경쟁사 보도자료 5건 비교", "frequency": "weekly"})
        profile = (await c.call_tool("get_my_profile", {})).structured_content
    titles = {t["title"] for t in profile["tasks"]}
    assert "보도자료 비교(수정)" in titles and profile["employee"]["id"] == "emp_mkt_01"


# ---------- F2 모델 선택 ----------

async def test_f2_eval_then_cost(monkeypatch):
    async with connect(mcp, monkeypatch, "cs") as c:
        evals = (await c.call_tool("get_eval_results", {"task_type": "customer_inquiry_classification"})).structured_content
        passed = [r["model_id"] for r in evals["results"] if r["passed"]]
        assert passed == ["anthropic:claude-opus-5-5", "anthropic:claude-sonnet-5-5"]
        costs = {}
        for model_id in passed:
            est = (await c.call_tool("estimate_task_cost", {"model_id": model_id, "requests_per_day": 1000,
                                                            "avg_input_tokens": 600, "avg_output_tokens": 20})).structured_content
            costs[model_id] = est["monthly"]["krw"]
            assert "formula" in est and est["fx_rate_krw_per_usd"] > 0
        assert costs["anthropic:claude-sonnet-5-5"] < costs["anthropic:claude-opus-5-5"]
        none_confidential = (await c.call_tool("list_approved_models", {"data_class": "confidential"})).structured_content
    assert none_confidential["models"] == []


# ---------- F3 사용량 경보 ----------

async def test_f3_anomaly_breakdown(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        anomalies = (await c.call_tool("get_anomalies", {"status": "open"})).structured_content["anomalies"]
        project = anomalies[0]["scope_id"]
        rows = (await c.call_tool("get_usage_breakdown", {"project_id": project, "period": PERIOD,
                                                          "by": "input_length"})).structured_content["rows"]
        summary = (await c.call_tool("get_usage_summary", {"scope": "project", "scope_id": project,
                                                           "period": PERIOD})).structured_content
    assert project == "prj_quote_summary" and anomalies[0]["ratio"] > 3
    assert max(rows, key=lambda r: r["share"])["key"] == "8k+"
    assert summary["cost"]["krw"] > 0


async def test_f3_employee_cannot_see_project_usage(monkeypatch):
    async with connect(mcp, monkeypatch, "employee") as c:
        result = await c.call_tool("get_usage_summary", {"scope": "project", "scope_id": "prj_quote_summary",
                                                         "period": PERIOD}, raise_on_error=False)
    assert error_of(result)["code"] == "forbidden"


# ---------- F4 이용권 · 조치안 실행 게이트 ----------

async def test_f4_plan_lifecycle(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        inventory = (await c.call_tool("get_license_inventory", {})).structured_content["contracts"][0]
        assert inventory["unassigned"] == 2
        flags = {cand["flag"] for cand in inventory["low_usage_candidates"] if cand["needs_confirmation"]}
        assert "no_record" in flags                                    # 기록 없음은 확인 필요

        plan = (await c.call_tool("create_action_plan", {
            "type": "seat_reclaim", "items": [{"employee_id": "emp_sales_02", "contract_id": "ctr_chatgpt_2026"}],
            "rationale": "휴직 중, 본인 확인 응답: 반납",
            "evidence": [{"source": "confirmations", "ref": "cfm_001", "value": "return_seat"}]})).structured_content
        assert plan["status"] == "pending_approval" and plan["approvers_required"] == ["admin"]

        early = await c.call_tool("execute_approved_plan", {"plan_id": plan["plan_id"], "idempotency_key": "mcp-k1"},
                                  raise_on_error=False)
        assert error_of(early)["code"] == "forbidden"                 # 승인 전 실행 불가

        await backend_post(f"/plans/{plan['plan_id']}/approve", "asset", {"reason": "본인 반납 응답"})
        first = (await c.call_tool("execute_approved_plan", {"plan_id": plan["plan_id"],
                                                             "idempotency_key": "mcp-k1"})).structured_content
        again = (await c.call_tool("execute_approved_plan", {"plan_id": plan["plan_id"],
                                                             "idempotency_key": "mcp-k1"})).structured_content
        status = (await c.call_tool("get_plan_status", {"plan_id": plan["plan_id"]})).structured_content
    assert first == again and first["status"] == "executed" and first["verified"]["state"] == "applied"
    assert status["plan"]["status"] == "executed"


async def test_f4_high_risk_is_decided_by_admin(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        plan = (await c.call_tool("create_action_plan", {"type": "purchase_review", "items": [{"tool_id": "tool_grok"}],
                                                         "rationale": "계약서 비교 수요 3건", "evidence": []})).structured_content
    assert plan["risk_level"] == "high" and plan["approvers_required"] == ["admin"]


# ---------- Resource · Prompt ----------

async def test_resources_and_prompts_match_spec(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        uris = {str(r.uri) for r in await c.list_resources()} | {t.uri_template for t in await c.list_resource_templates()}
        prompts = {p.name: [a.name for a in p.arguments] for p in await c.list_prompts()}
        policy = (await c.read_resource("policy://ai-usage"))[0].text
        contract = (await c.read_resource("contract://ctr_chatgpt_2026/summary"))[0].text
        matrix = (await c.read_resource("policy://approval-matrix"))[0].text
        rendered = await c.get_prompt("investigate_anomaly", {"anomaly_id": "anm_001"})
    assert uris == set(RESOURCES)
    assert prompts == PROMPTS
    assert "제5조 이용권 회수" in policy and "제8조 개인정보" in policy and '"unassigned": 2' in contract
    assert "| 테스트 환경 모델 변경 (model_change) | 담당자 승인 | 관리자 | 승인 후 실행 |" in matrix
    assert "본인 확인 응답 필수" in matrix and "(purchase_review) | 책임자 결정" in matrix
    text = rendered.messages[0].content.text
    assert "anm_001" in text and "execute_approved_plan을 부르지 않는다" in text


async def test_prompt_requires_arguments(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        with pytest.raises(MCPError, match="plan_id"):
            await c.get_prompt("review_seat_request", {})


def test_instructions_include_plan_item_formats():
    assert "model_change: {project_id, from_model_id, to_model_id, environment?}" in mcp.instructions


async def test_invalid_plan_items_rejected_by_backend(monkeypatch):
    async with connect(mcp, monkeypatch, "asset") as c:
        result = await c.call_tool("create_action_plan", {"type": "model_change", "items": [{"project_id": "prj_faq"}],
                                                          "rationale": "x", "evidence": []}, raise_on_error=False)
    assert error_of(result)["code"] == "invalid"


@pytest.mark.parametrize("name, args, principle", [
    ("investigate_anomaly", {"anomaly_id": "anm_001"}, "원인을 단정하지 말고"),
    ("review_seat_request", {"plan_id": "plan_002"}, "무응답은 회수 사유로 쓰지 않는다"),
    ("review_update", {"update_id": "upd_chatgpt_doc_compare"}, "save_suggestion(status=on_hold, hold_reason)"),
    ("recommend_model", {"task_description": "문의 분류"}, "평가 결과가 없으면 추천하지 말고"),
    ("recommend_model", {"task_description": "문의 분류"}, "현재 모델도 estimate_task_cost로 계산"),
    ("investigate_anomaly", {"anomaly_id": "anm_001"}, "get_anomaly_detail로 대상 프로젝트의 등록 목적"),
    ("review_seat_request", {"plan_id": "plan_002"}, "이미 executed면 다시 실행하지 말고"),
    ("review_seat_request", {"plan_id": "plan_002"}, "create_action_plan(seat_reclaim, items=[{employee_id, contract_id, confirmation_id"),
])
async def test_prompts_carry_design_principles(monkeypatch, name, args, principle):
    """설계 문서 7절 Prompt 표의 '담긴 판단 원칙'이 템플릿에 들어 있다."""
    async with connect(mcp, monkeypatch, "asset") as c:
        rendered = await c.get_prompt(name, args)
    assert principle in rendered.messages[0].content.text


async def test_prompts_only_mention_registered_tools():
    """Prompt가 안내하는 도구 이름이 실제 명세에 있어야 한다 (명세에서 도구 이름이 바뀌면 여기서 걸린다)."""
    import re

    from schemas.mcp_tools import TOOLS

    from apps.mcp_work.prompts import TEMPLATES
    tool_names = {t.name for t in TOOLS}
    verbs = ("get_", "list_", "search_", "save_", "create_", "execute_", "estimate_", "record_", "request_", "find_",
             "upsert_")
    for name, template in TEMPLATES.items():
        mentioned = {w for w in re.findall(r"[a-z]+_[a-z_]+", template) if w.startswith(verbs)}
        assert mentioned <= tool_names, (name, mentioned - tool_names)


async def test_role_cache_expires(monkeypatch):
    from apps.mcp_work import auth, backend
    calls = []
    real_call = backend.call

    async def counting_call(method, path, **kwargs):
        if path == "/me":
            calls.append(path)
        return await real_call(method, path, **kwargs)

    monkeypatch.setattr(backend, "call", counting_call)
    async with connect(mcp, monkeypatch, "asset") as c:
        monkeypatch.setattr(auth, "ROLE_CACHE_SECONDS", 300)
        await c.list_tools()
        await c.list_tools()
        assert len(calls) == 1                                  # 캐시 안이면 백엔드에 다시 묻지 않는다
        monkeypatch.setattr(auth, "ROLE_CACHE_SECONDS", 0)
        await c.list_tools()
        assert len(calls) == 2                                  # 만료되면 다시 확인한다
