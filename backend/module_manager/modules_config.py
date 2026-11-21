"""Declarative registration of CITADEL tool modules.

To add a future module (e.g., Module 02), drop its package inside ``modules/``,
implement ``create_router()``, and register a new ``ModuleDefinition`` below.
No changes to ``main.py`` or the Tools Library layout are required.
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
                version="1.0.0",
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
                    "Multi-File & Batch ZIP Extraction",
                ],
            )
        )

    registry.mount_all(app)
