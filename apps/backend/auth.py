"""MVP 인증. 토큰은 'dev.<employee_id>' 형태. 후속 단계에서 JWT/OAuth로 교체."""

from __future__ import annotations

from fastapi import Depends, Header

from apps.backend import db
from apps.backend.errors import ApiError
from schemas.common import ErrorCode, Role
from schemas.entities import Employee

PREFIX = "dev."


def issue_token(employee_id: str) -> str:
    return PREFIX + employee_id


def get_employee(employee_id: str) -> Employee | None:
    r = db.one("SELECT e.*, d.name AS dept_name FROM employees e JOIN departments d ON d.id = e.dept_id WHERE e.id = :id", id=employee_id)
    return Employee(**r) if r else None


def current_user(authorization: str | None = Header(default=None)) -> Employee:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(ErrorCode.unauthorized, "Authorization: Bearer <token> 헤더가 필요합니다")
    token = authorization.split(" ", 1)[1].strip()
    if not token.startswith(PREFIX):
        raise ApiError(ErrorCode.unauthorized, "토큰 형식이 잘못됐습니다")
    emp = get_employee(token[len(PREFIX):])
    if not emp:
        raise ApiError(ErrorCode.unauthorized, "알 수 없는 직원 토큰입니다")
    return emp


def require(*roles: Role):
    """역할 검사 의존성. 3절 권한 매트릭스를 엔드포인트 단위로 적용한다."""

    def dep(user: Employee = Depends(current_user)) -> Employee:
        if user.role not in roles:
            raise ApiError(
                ErrorCode.forbidden,
                f"{user.role.value} 역할은 이 작업을 할 수 없습니다",
                {"allowed_roles": [r.value for r in roles]},
            )
        return user

    return dep
