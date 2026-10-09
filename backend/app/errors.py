"""One error envelope for the whole API: {error, reason?, fields?}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, status: int, error: str, reason: str | None = None,
                 fields: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> None:
        super().__init__(error)
        self.status, self.error, self.reason = status, error, reason
        self.fields, self.headers = fields, headers


def _body(error: str, reason: str | None = None, fields: dict[str, str] | None = None) -> dict:
    body: dict = {"error": error}
    if reason:
        body["reason"] = reason
    if fields:
        body["fields"] = fields
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.error, exc.reason, exc.fields), status_code=exc.status,
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = {".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]): e["msg"] for e in exc.errors()}
        return JSONResponse(_body("validation_error", fields=fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        error = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(_body(error), status_code=exc.status_code, headers=exc.headers)
