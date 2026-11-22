"""CITADEL FastAPI router adapter for Module 02: DocReader."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

DOCREADER_ROOT = Path(__file__).resolve().parent
if str(DOCREADER_ROOT) not in sys.path:
    sys.path.insert(0, str(DOCREADER_ROOT))

from app.api.routes import router as docreader_api_router  # noqa: E402
from app.config import settings as docreader_settings  # noqa: E402
from app.security.file_validator import DocumentError  # noqa: E402
from app.services.cleanup_service import cleanup_loop  # noqa: E402


def register_exception_handlers(app) -> None:
    """Register DocReader DocumentError handler on the parent CITADEL FastAPI app."""

    @app.exception_handler(DocumentError)
    async def docreader_error_handler(_request: Request, exc: DocumentError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "detail": {"code": exc.code, "message": exc.message},
            },
        )


def create_router() -> APIRouter:
    """Return the DocReader APIRouter mounted under /api/modules/docreader."""
    try:
        docreader_settings.ensure_dirs()
    except Exception:
        pass
    return docreader_api_router


__all__ = ["create_router", "register_exception_handlers", "cleanup_loop", "docreader_settings"]
