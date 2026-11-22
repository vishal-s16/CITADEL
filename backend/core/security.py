"""Security middleware and safe upload helpers for CITADEL."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach conservative HTTP security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # SAMEORIGIN allows CITADEL's SPA to embed its own module UIs while blocking external clickjacking
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        return response


def error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    """Return a consistent, sanitized JSON error payload without exposing server internals."""
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error_type": error_type,
            "message": message,
        },
    )
