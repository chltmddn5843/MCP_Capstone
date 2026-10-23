"""Resource 6개 (schemas.mcp_tools.RESOURCES). 읽기 전용 자료를 주소로 제공한다.

policy://* 는 문서 MCP와 같은 사내 정책 원문(apps.mcp_docs.corpus)을 읽고,
나머지는 백엔드 REST를 요청자 토큰으로 부른다.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError
from schemas.common import RISK_BY_PLAN_TYPE, PlanType, RiskLevel
from schemas.mcp_tools import RESOURCES

from apps.mcp_docs.corpus import load_corpus
from apps.mcp_work.backend import call


def _policy(doc_id: str) -> str:
    doc = load_corpus().get(doc_id)
    if doc is None:
        raise ResourceError(f"정책 문서 {doc_id}가 없습니다.")
    return doc.raw


# 설계 문서 11절 승인 기준표의 조치 이름·승인자·MVP 처리. 위험도는 RISK_BY_PLAN_TYPE에서 읽는다.
APPROVAL_ROWS: dict[PlanType, tuple[str, str, str]] = {  # v2: 관리자 한 명이 담당자 승인과 책임자 결정을 모두 한다
    PlanType.seat_assign: ("이용권 배정", "관리자 (남은 좌석이 있으면 시스템이 바로 배정)", "승인 후 실행"),
    PlanType.seat_reclaim: ("이용권 회수·재배정·반납", "관리자 (회수는 본인 확인 응답 필수)", "승인 후 실행"),
    PlanType.api_access: ("API 제품 사용 신청", "관리자", "승인 후 프로젝트 생성"),
    PlanType.model_change: ("테스트 환경 모델 변경", "관리자", "승인 후 실행"),
    PlanType.budget_review: ("예산 증액 검토", "관리자 (사용 목적 확인 후)", "승인 후 실행"),
    PlanType.purchase_review: ("이용권 추가 구매·신규 제품 도입", "관리자 (책임자 결정)", "요청만 생성, 실행 안 함"),
}
RISK_KO = {RiskLevel.low: "바로 처리", RiskLevel.medium: "담당자 승인", RiskLevel.high: "책임자 결정"}


def _approval_matrix() -> str:
    lines = ["# 승인 기준 (설계 문서 v2 11절)", "",
             "에이전트가 만드는 처리 요청은 관리자 승인을 거친다. 예외로 남은 좌석이 있는 이용권 배정(seat_assign)은 서버가 바로 배정한다(status=executed). "
             "되돌릴 수 없는 비용이 생기는 일은 승인돼도 실행하지 않고 요청만 남긴다.", "",
             "| 처리 요청 (type) | 단계 | 누가 | MVP 처리 |", "|---|---|---|---|",
             "| 개인 맞춤 활용 제안 발송 (save_suggestion, target_type=employee) | 낮음 | 알림 정책 | 자동 |"]
    for plan_type, risk in RISK_BY_PLAN_TYPE.items():
        name, approver, handling = APPROVAL_ROWS[plan_type]
        lines.append(f"| {name} ({plan_type.value}) | {RISK_KO[risk]} | {approver} | {handling} |")
    lines += ["| 운영 환경 모델 변경 (model_change, environment=prod) | 책임자 결정 | 관리자 | 요청만 생성, 실행 안 함 |",
              "", "직원은 seat_assign(본인)과 model_change(본인이 오너인 프로젝트, test 환경)만 만들 수 있다.",
              "실행은 승인된 plan_id로만 하며, 서버가 실행 직전에 승인 상태와 대상의 현재 상태를 다시 확인한다(다르면 stale)."]
    return "\n".join(lines)


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def register_resources(mcp: FastMCP) -> None:
    @mcp.resource("policy://ai-usage", description=RESOURCES["policy://ai-usage"], mime_type="text/markdown")
    def ai_usage() -> str:
        return _policy("policy-ai-usage")

    @mcp.resource("policy://notification", description=RESOURCES["policy://notification"], mime_type="text/markdown")
    def notification() -> str:
        return _policy("policy-notification")

    @mcp.resource("policy://approval-matrix", description=RESOURCES["policy://approval-matrix"], mime_type="text/markdown")
    def approval_matrix() -> str:
        return _approval_matrix()

    @mcp.resource("catalog://approved-tools", description=RESOURCES["catalog://approved-tools"], mime_type="application/json")
    async def approved_tools() -> str:
        return _json(await call("GET", "/tools"))

    @mcp.resource("contract://{id}/summary", description=RESOURCES["contract://{id}/summary"], mime_type="application/json")
    async def contract_summary(id: str) -> str:
        rows = await call("GET", "/inventory", params={"contract_id": id})
        if not rows:
            raise ResourceError(f"계약 {id}가 없거나 볼 권한이 없습니다.")
        inv = rows[0]
        return _json({"contract": inv["contract"], "tool_name": inv["tool_name"], "purchased": inv["purchased"],
                      "assigned": inv["assigned"], "unassigned": inv["unassigned"],
                      "low_usage_candidates": len(inv["low_usage_candidates"])})

    @mcp.resource("me://profile", description=RESOURCES["me://profile"], mime_type="application/json")
    async def my_profile() -> str:
        return _json(await call("GET", "/me"))
