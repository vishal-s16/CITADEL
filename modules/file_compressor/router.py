"""CITADEL FastAPI router adapter for Module 03: Universal File Compressor."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

COMPRESSOR_ROOT = Path(__file__).resolve().parent
if str(COMPRESSOR_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPRESSOR_ROOT))

from compressor_backend.routes.compression import router as compression_router  # noqa: E402
from compressor_backend.utils.file_cleanup import AutoCleanupWorker  # noqa: E402

cleanup_worker = AutoCleanupWorker(max_age_seconds=1800, interval_seconds=300)


def create_router() -> APIRouter:
    """Return the Universal File Compressor APIRouter mounted under /api/modules/compressor."""
    return compression_router


__all__ = ["create_router", "cleanup_worker"]
