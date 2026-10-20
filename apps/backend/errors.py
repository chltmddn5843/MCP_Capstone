from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from schemas.common import HTTP_STATUS_BY_CODE, ErrorCode


class ApiError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        self.code, self.message, self.details = code, message, details


def ok(data, request_id: str | None = None) -> dict:
    """성공 봉투. 라우터는 항상 이 함수로 감싸 돌려준다."""
    return {"data": data, "meta": {"request_id": request_id or uuid.uuid4().hex[:12]}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        body = {"error": {"code": exc.code.value, "message": exc.message, "details": exc.details}}
        return JSONResponse(status_code=HTTP_STATUS_BY_CODE[exc.code], content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        body = {"error": {"code": "invalid", "message": "입력 검증 실패", "details": {"errors": exc.errors()}}}
        return JSONResponse(status_code=422, content=body)
