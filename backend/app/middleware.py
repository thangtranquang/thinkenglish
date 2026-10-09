"""Security headers on every response; API responses are never cached."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response


class UploadSizeLimitMiddleware:
    """Reject POST /api/uploads with an oversized Content-Length before the multipart body is parsed.

    Chunked bodies without Content-Length are not capped here; the service still enforces the byte limit.
    """
    SLACK = 64 * 1024

    def __init__(self, app, max_upload_bytes: int) -> None:
        self.app, self.limit = app, max_upload_bytes + self.SLACK

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == "/api/uploads":
            raw = dict(scope["headers"]).get(b"content-length", b"")
            if raw.isdigit() and int(raw) > self.limit:
                await JSONResponse({"error": "image_too_large"}, status_code=413)(scope, receive, send)
                return
        await self.app(scope, receive, send)
