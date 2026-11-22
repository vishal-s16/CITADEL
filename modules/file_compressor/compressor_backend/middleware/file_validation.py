"""Binary magic-byte file validation and spoofing protection."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

SUPPORTED_FORMATS: dict[str, dict[str, Any]] = {
    "pdf": {"category": "pdf", "extensions": [".pdf"], "max_size_mb": 100},
    "jpg": {"category": "image", "extensions": [".jpg", ".jpeg"], "max_size_mb": 50},
    "png": {"category": "image", "extensions": [".png"], "max_size_mb": 50},
    "webp": {"category": "image", "extensions": [".webp"], "max_size_mb": 50},
    "mp4": {"category": "video", "extensions": [".mp4"], "max_size_mb": 200},
    "mov": {"category": "video", "extensions": [".mov"], "max_size_mb": 200},
    "docx": {"category": "document", "extensions": [".docx"], "max_size_mb": 100},
    "pptx": {"category": "document", "extensions": [".pptx"], "max_size_mb": 100},
    "zip": {"category": "archive", "extensions": [".zip"], "max_size_mb": 200},
}

ALL_ALLOWED_EXTENSIONS = {
    ext for meta in SUPPORTED_FORMATS.values() for ext in meta["extensions"]
}

MAX_GLOBAL_FILE_SIZE_BYTES = int(os.environ.get("MAX_FILE_SIZE_MB", "200")) * 1024 * 1024


def sanitize_filename(original_name: str | None) -> str:
    base = Path(str(original_name or "file")).name
    cleaned = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "_", base)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:180] if cleaned else "uploaded_file"


def _inspect_zip_subtype(file_path: Path) -> str:
    size = file_path.stat().st_size
    read_size = min(size, 256 * 1024)
    with file_path.open("rb") as f:
        head = f.read(read_size)
        tail = b""
        if size > read_size:
            tail_size = min(size, 256 * 1024)
            f.seek(size - tail_size)
            tail = f.read(tail_size)
    combined = (head + tail).decode("latin1", errors="ignore")
    if "word/document.xml" in combined:
        return "docx"
    if "ppt/presentation.xml" in combined:
        return "pptx"
    return "zip"


def detect_file_format(file_path: Path, original_name: str = "") -> str | None:
    if not file_path.is_file() or file_path.stat().st_size < 4:
        return None

    with file_path.open("rb") as f:
        header = f.read(32)

    ext = Path(original_name).suffix.lower()

    if header[:5] == b"%PDF-":
        return "pdf"
    if header[:3] == b"\xff\xd8\xff":
        return "jpg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand == b"qt  " or ext == ".mov":
            return "mov"
        return "mp4"
    if len(header) >= 8 and header[4:8] in (b"moov", b"mdat", b"wide", b"free") and ext == ".mov":
        return "mov"
    if header[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        return _inspect_zip_subtype(file_path)
    return None


def validate_uploaded_file(file_path: Path, original_name: str) -> dict[str, Any]:
    sanitized = sanitize_filename(original_name)
    ext = Path(sanitized).suffix.lower()

    if ext not in ALL_ALLOWED_EXTENSIONS:
        return {
            "valid": False,
            "error": f'Unsupported file extension "{ext or "none"}". Supported: PDF, JPG, JPEG, PNG, WEBP, MP4, MOV, DOCX, PPTX, ZIP.',
        }

    actual_size = file_path.stat().st_size if file_path.exists() else 0
    if actual_size <= 0:
        return {"valid": False, "error": "The uploaded file is empty (0 bytes)."}

    if actual_size > MAX_GLOBAL_FILE_SIZE_BYTES:
        return {
            "valid": False,
            "error": f"File exceeds the maximum allowed size of {MAX_GLOBAL_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        }

    detected = detect_file_format(file_path, sanitized)
    if not detected or detected not in SUPPORTED_FORMATS:
        return {
            "valid": False,
            "error": "File content does not match any supported format or appears corrupted.",
        }

    expected_exts = SUPPORTED_FORMATS[detected]["extensions"]
    video_compatible = (detected == "mp4" and ext == ".mov") or (detected == "mov" and ext == ".mp4")
    if ext not in expected_exts and not video_compatible:
        return {
            "valid": False,
            "error": f'File signature mismatch: extension is "{ext}" but binary content is "{detected.upper()}". Spoofed files are rejected.',
        }

    max_fmt_bytes = SUPPORTED_FORMATS[detected]["max_size_mb"] * 1024 * 1024
    if actual_size > max_fmt_bytes:
        return {
            "valid": False,
            "error": f'{detected.upper()} files are limited to {SUPPORTED_FORMATS[detected]["max_size_mb"]} MB.',
        }

    return {
        "valid": True,
        "format": detected,
        "category": SUPPORTED_FORMATS[detected]["category"],
        "sanitizedName": sanitized,
        "size": actual_size,
    }
