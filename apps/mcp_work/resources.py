"""Resource 6개 (schemas.mcp_tools.RESOURCES). 읽기 전용 자료를 주소로 제공한다.

policy://* 는 문서 MCP와 같은 사내 정책 원문(apps.mcp_docs.corpus)을 읽고,
나머지는 백엔드 REST를 요청자 토큰으로 부른다.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError
from schemas.common import RISK_BY_PLAN_TYPE
from schemas.mcp_tools import RESOURCES

from apps.mcp_docs.corpus import load_corpus
from apps.mcp_work.backend import call


def _policy(doc_id: str) -> str:
    doc = load_corpus().get(doc_id)
    if doc is None:
        raise ResourceError(f"정책 문서 {doc_id}가 없습니다.")
    return doc.raw


def _approval_matrix() -> str:
    lines = ["# 위험도별 승인 기준 (11절, schemas.common.RISK_BY_PLAN_TYPE 기준)", "",
             "| 조치 유형 | 위험도 | 승인 |", "|---|---|---|"]
    who = {"low": "자동 승인", "medium": "자산관리(공지 발송은 HRD)", "high": "IT·보안 책임자(approver), MVP에서 실행 안 함"}
    for plan_type, risk in RISK_BY_PLAN_TYPE.items():
        lines.append(f"| {plan_type.value} | {risk.value} | {who[risk.value]} |")
    lines += ["", "model_change는 environment=prod 항목이 있으면 high로 올라간다."]
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
