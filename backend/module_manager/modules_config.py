"""Declarative registration of CITADEL tool modules.

Each module lives inside ``modules/``, exposes ``create_router()``, and is
registered as a ``ModuleDefinition`` below so the Tools Library renders it
automatically.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from fastapi import FastAPI

from backend.core.config import MODULES_DIR
from backend.module_manager.registry import (
    ModuleBackendConfig,
    ModuleDefinition,
    ModuleRegistry,
)


def _load_module_router(router_path: Path, unique_name: str) -> ModuleType:
    """Dynamically load a module's router.py without polluting global namespaces."""
    spec = importlib.util.spec_from_file_location(unique_name, str(router_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module router from {router_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def register_all_modules(registry: ModuleRegistry, app: FastAPI) -> None:
    """Register all active CITADEL modules and mount their APIs."""
    # MODULE 01: Steganography System
    steg_router_mod = _load_module_router(
        MODULES_DIR / "steganography_system" / "router.py",
        "citadel_mod_steganography_router",
    )
    steg_router_mod.register_exception_handlers(app)

    if registry.get("steganography-system") is None:
        registry.register(
            ModuleDefinition(
                module_id="steganography-system",
                code="MODULE 01",
                name="Steganography System",
                description="Securely hide digital files inside images and retrieve them when needed.",
                category="Security / File Protection",
                icon="shield-layers",
                entry_route="/tools/steganography",
                status="Available",
                version="1.1.0",
                backend=ModuleBackendConfig(
                    api_prefix="/api/modules/steganography",
                    legacy_api_prefix="/api",
                    router_factory=steg_router_mod.create_router,
                    health_endpoint="/api/modules/steganography/health",
                ),
                capabilities=[
                    "RGB LSB Lossless Embedding",
                    "zlib Compression",
                    "Optional AES-256-GCM Encryption",
                    "PBKDF2-HMAC-SHA256 Key Derivation",
                    "SHA-256 & CRC32 Integrity Verification",
                    "Large-File Chunked Extraction",
                ],
            )
        )

    # MODULE 02: DocReader
    docreader_router_mod = _load_module_router(
        MODULES_DIR / "docreader" / "router.py",
        "citadel_mod_docreader_router",
    )
    docreader_router_mod.register_exception_handlers(app)
    app.state.module_lifespan["docreader_settings"] = docreader_router_mod.docreader_settings
    app.state.module_lifespan["docreader_cleanup_loop"] = docreader_router_mod.cleanup_loop

    if registry.get("docreader") is None:
        registry.register(
            ModuleDefinition(
                module_id="docreader",
                code="MODULE 02",
                name="DocReader",
                description="All-in-one AI document reader supporting PDF, Office, spreadsheets, images, OCR, search, and text-to-speech.",
                category="Documents / AI Intelligence",
                icon="file-text",
                entry_route="/tools/docreader",
                status="Available",
                version="1.0.0",
                backend=ModuleBackendConfig(
                    api_prefix="/api/modules/docreader",
                    router_factory=docreader_router_mod.create_router,
                    health_endpoint="/api/modules/docreader/health",
                ),
                capabilities=[
                    "PDF, Word, Excel & PowerPoint",
                    "Built-in OCR & Page Renderer",
                    "Full-Text Search & Highlights",
                    "AI Summary & Q&A Assistant",
                    "Web Speech Text-to-Speech",
                    "Instant .TXT Export",
                ],
            )
        )

    # MODULE 03: Universal File Compressor
    compressor_router_mod = _load_module_router(
        MODULES_DIR / "file_compressor" / "router.py",
        "citadel_mod_compressor_router",
    )
    app.state.module_lifespan["compressor_cleanup_worker"] = compressor_router_mod.cleanup_worker

    if registry.get("file-compressor") is None:
        registry.register(
            ModuleDefinition(
                module_id="file-compressor",
                code="MODULE 03",
                name="Universal File Compressor",
                description="Smart hybrid client & server file compressor for images, PDFs, Office docs, audio, video, and archives.",
                category="Utilities / Optimization",
                icon="compress",
                entry_route="/tools/compressor",
                status="Available",
                version="1.0.0",
                backend=ModuleBackendConfig(
                    api_prefix="/api/modules/compressor",
                    router_factory=compressor_router_mod.create_router,
                    health_endpoint="/api/modules/compressor/health",
                ),
                capabilities=[
                    "Target File Size Mode",
                    "Image, PDF & Office Compression",
                    "Audio & Video Optimization",
                    "ZIP / Archive Re-Compression",
                    "Before & After Preview",
                    "Auto Temp File Cleanup",
                ],
            )
        )

    registry.mount_all(app)
