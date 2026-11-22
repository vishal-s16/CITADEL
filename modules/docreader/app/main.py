"""DOCREADER FastAPI application entry point."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .api.routes import router as api_router
from .config import settings
from .security.file_validator import DocumentError
from .services.cleanup_service import cleanup_loop

STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.ensure_dirs()
    cleanup_task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="All-in-One AI-Powered Document Reader API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DocumentError)
async def document_error_handler(_request: Request, exc: DocumentError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


app.include_router(api_router)


@app.get("/", include_in_schema=False)
def serve_web_app():
    """Serve the built-in zero-Node web UI directly from FastAPI."""
    if STATIC_INDEX.exists():
        return FileResponse(str(STATIC_INDEX), media_type="text/html")
    return {"app": settings.app_name, "version": settings.app_version, "docs": "/docs"}
