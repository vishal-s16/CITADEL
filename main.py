"""CITADEL — Centralized Multi-Tool Web Platform Entry Point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import (
    ASSETS_DIR,
    DEFAULT_HOST,
    DEFAULT_PORT,
    FRONTEND_DIR,
    MODULES_DIR,
    PLATFORM_NAME,
    PLATFORM_TAGLINE,
    PLATFORM_VERSION,
)
from backend.core.security import SecurityHeadersMiddleware, error_response
from backend.module_manager.modules_config import register_all_modules
from backend.module_manager.registry import ModuleRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage background cleanup tasks for integrated modules."""
    hooks = getattr(app.state, "module_lifespan", {})
    docreader_settings = hooks.get("docreader_settings")
    docreader_cleanup_loop = hooks.get("docreader_cleanup_loop")
    compressor_cleanup_worker = hooks.get("compressor_cleanup_worker")

    docreader_task = None
    if docreader_settings is not None:
        docreader_settings.ensure_dirs()
    if docreader_cleanup_loop is not None:
        docreader_task = asyncio.create_task(docreader_cleanup_loop())
    if compressor_cleanup_worker is not None:
        compressor_cleanup_worker.start()

    try:
        yield
    finally:
        if compressor_cleanup_worker is not None:
            compressor_cleanup_worker.stop()
        if docreader_task is not None:
            docreader_task.cancel()
            try:
                await docreader_task
            except asyncio.CancelledError:
                pass


def create_app() -> FastAPI:
    """Create and configure the unified CITADEL FastAPI application."""
    app = FastAPI(
        title=PLATFORM_NAME,
        description=PLATFORM_TAGLINE,
        version=PLATFORM_VERSION,
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)

    # Centralized Module Registry
    module_registry = ModuleRegistry()
    app.state.module_registry = module_registry
    app.state.module_lifespan = {}

    # --- Global Safe Exception Handlers ---
    @app.exception_handler(MemoryError)
    async def memory_error_handler(_request: Request, _exc: MemoryError) -> JSONResponse:
        return error_response(
            507,
            "MemoryError",
            "Insufficient memory to complete this operation. Try a smaller image or smaller files.",
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return error_response(
            500,
            "UnexpectedError",
            "An unexpected error occurred while processing your request. Please verify your inputs and try again.",
        )

    # --- Core Platform API Endpoints (registered before module routers) ---
    @app.get("/api/health")
    async def platform_health():
        return {
            "ok": True,
            "platform": PLATFORM_NAME,
            "version": PLATFORM_VERSION,
            "registered_modules": len(module_registry.list_modules()),
        }

    @app.get("/api/modules")
    async def list_registered_modules():
        """Return all registered tool modules for the CITADEL Tool Library."""
        return {
            "ok": True,
            "platform": PLATFORM_NAME,
            "modules": [m.to_public_dict() for m in module_registry.list_modules()],
        }

    @app.get("/api/modules/{module_id}")
    async def get_registered_module(module_id: str):
        module = module_registry.get(module_id)
        if module is None:
            return error_response(404, "ModuleNotFound", f"Module '{module_id}' is not registered.")
        return {
            "ok": True,
            "module": module.to_public_dict(),
        }

    # Register and mount all independent modules
    register_all_modules(module_registry, app)

    # --- Embedded Module UIs (same-origin) ---
    docreader_index = MODULES_DIR / "docreader" / "app" / "static" / "index.html"
    compressor_frontend_dir = MODULES_DIR / "file_compressor" / "frontend"

    @app.get("/module-ui/docreader", include_in_schema=False)
    @app.get("/module-ui/docreader/", include_in_schema=False)
    async def serve_docreader_ui():
        return FileResponse(docreader_index, media_type="text/html")

    app.mount(
        "/module-ui/compressor",
        StaticFiles(directory=str(compressor_frontend_dir), html=True),
        name="citadel_compressor_ui",
    )

    # --- Static Frontend & Asset Mounts ---
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="citadel_assets")
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="citadel_frontend")

    # Favicon shortcut
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(ASSETS_DIR / "logos" / "favicon.png", media_type="image/png")

    # --- SPA Catch-All Route (enables seamless client-side navigation & continuous audio) ---
    index_html = FRONTEND_DIR / "index.html"

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str = ""):
        # Never swallow unknown /api/* paths
        if full_path.startswith("api/") or full_path == "api":
            return error_response(404, "NotFound", "The requested API endpoint does not exist.")
        return FileResponse(index_html, media_type="text/html")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)
