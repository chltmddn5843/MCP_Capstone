"""Slack 사용자 → 직원 토큰.

1순위: 백엔드 `POST /auth/slack-exchange` (시스템 토큰으로 호출, 아키텍처 v3 JWT 전환 뒤 백엔드가 제공 예정).
2순위(지금): SLACK_USER_MAP(JSON: slack_user_id → employee_id)으로 dev-login. 비어 있으면 시드의 slack_user_id로 역조회.
토큰은 메모리에만 캐시한다.
"""

from __future__ import annotations

import json
import os
import time

import requests

from apps.slack_bot.client import BACKEND_URL, ApiError, backend

SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN", "dev.sys")
_cache: dict[str, tuple[float, str, dict]] = {}  # slack_user_id -> (expires, token, employee)
TTL = 3600


def _user_map() -> dict[str, str]:
    raw = os.getenv("SLACK_USER_MAP", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def _dev_login(employee_id: str) -> tuple[str, dict]:
    r = requests.post(f"{BACKEND_URL}/auth/dev-login", json={"employee_id": employee_id}, timeout=10).json()
    if "error" in r:
        raise ApiError(r["error"]["code"], r["error"]["message"])
    return r["data"]["access_token"], r["data"]["employee"]


def resolve(slack_user_id: str) -> tuple[str, dict]:
    """(토큰, 직원) 을 돌려준다. 매핑이 없으면 ApiError(not_found)."""
    hit = _cache.get(slack_user_id)
    if hit and hit[0] > time.time():
        return hit[1], hit[2]
    token = employee = None
    try:  # 1순위: 백엔드 교환 (아직 없으면 not_found → 다음 순위)
        d = backend("POST", "/auth/slack-exchange", SYSTEM_TOKEN, json={"slack_user_id": slack_user_id})
        token, employee = d["access_token"], d["employee"]
    except (ApiError, requests.exceptions.RequestException):
        pass
    if token is None:
        emp_id = _user_map().get(slack_user_id)
        if emp_id is None:
            raise ApiError("not_found", f"Slack 사용자 {slack_user_id} 에 연결된 직원이 없습니다. SLACK_USER_MAP을 확인하세요.")
        token, employee = _dev_login(emp_id)
    _cache[slack_user_id] = (time.time() + TTL, token, employee)
    return token, employee


def admin_slack_ids() -> list[str]:
    """관리자 알림을 받을 Slack 사용자. SLACK_ADMIN_USER_IDS(쉼표 구분)."""
    return [s.strip() for s in os.getenv("SLACK_ADMIN_USER_IDS", "").split(",") if s.strip()]
