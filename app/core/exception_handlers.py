from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.schemas.api_response import ApiResponse


def _http_error_payload(detail: Any) -> tuple[Any, str]:
    if isinstance(detail, str):
        return {"detail": detail}, detail
    if isinstance(detail, list):
        return {"detail": detail}, "Request failed"
    if isinstance(detail, dict):
        msg = detail.get("detail", detail.get("message", "Request failed"))
        if isinstance(msg, list):
            msg = "Request failed"
        return detail, str(msg)
    return {"detail": detail}, "Request failed"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        err_obj, msg = _http_error_payload(exc.detail)
        body = ApiResponse[Any](
            success=False,
            error=err_obj,
            data=None,
            message=msg,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(body),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        body = ApiResponse[Any](
            success=False,
            error={"errors": exc.errors()},
            data=None,
            message="Validation error",
        )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(body),
        )
