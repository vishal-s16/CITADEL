"""Core configuration for the CITADEL multi-tool platform."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
ASSETS_DIR = BASE_DIR / "assets"
MODULES_DIR = BASE_DIR / "modules"

PLATFORM_NAME = "CITADEL"
PLATFORM_VERSION = "1.0.0"
PLATFORM_TAGLINE = "One Platform. Multiple Possibilities."
CONTACT_EMAIL = "vishalsoundararajan16@gmail.com"

# Upload & processing limits (configurable via environment variables, never hardcoded secrets)
MAX_IMAGE_UPLOAD_BYTES = int(os.getenv("CITADEL_MAX_IMAGE_BYTES", str(30 * 1024 * 1024)))   # 30 MB
MAX_PAYLOAD_TOTAL_BYTES = int(os.getenv("CITADEL_MAX_PAYLOAD_BYTES", str(30 * 1024 * 1024))) # 30 MB
MAX_FILES_PER_REQUEST = int(os.getenv("CITADEL_MAX_FILES", "25"))

# Host & port defaults
DEFAULT_HOST = os.getenv("CITADEL_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("CITADEL_PORT", "8000"))
