"""File category definitions, extension validation, sanitization, and ZIP packaging."""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from modules.exceptions import EmptyFileSelectionError, UnsupportedFileExtensionError

FILE_CATEGORIES: Dict[str, dict] = {
    "text": {
        "id": "text",
        "label": "Text Files",
        "description": "Plain text, tabular, and structured data files",
        "extensions": ["txt", "csv", "json", "xml"],
    },
    "documents": {
        "id": "documents",
        "label": "Documents",
        "description": "Office documents and portable publications",
        "extensions": ["pdf", "doc", "docx", "rtf"],
    },
    "images": {
        "id": "images",
        "label": "Images",
        "description": "Raster graphics and picture files",
        "extensions": ["png", "jpg", "jpeg", "bmp", "gif"],
    },
    "audio": {
        "id": "audio",
        "label": "Audio",
        "description": "Compressed and lossless audio tracks",
        "extensions": ["mp3", "wav", "aac", "flac"],
    },
    "video": {
        "id": "video",
        "label": "Video",
        "description": "Video clips and multimedia containers",
        "extensions": ["mp4", "mkv", "avi", "mov"],
    },
    "archives": {
        "id": "archives",
        "label": "Archives",
        "description": "Compressed multi-file archive packages",
        "extensions": ["zip", "rar", "7z"],
    },
    "programming": {
        "id": "programming",
        "label": "Programming Files",
        "description": "Source code and web development files",
        "extensions": ["py", "c", "cpp", "java", "html", "css", "js"],
    },
    "other": {
        "id": "other",
        "label": "Other Files",
        "description": "Any other digital file format or extension",
        "extensions": ["*"],
    },
}


@dataclass(frozen=True)
class PayloadFile:
    """Represents a single file to be embedded or extracted."""

    filename: str
    extension: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)


def sanitize_filename(raw_filename: str) -> str:
    """Strip directory components and unsafe control characters while preserving extension."""
    base = os.path.basename((raw_filename or "").replace("\\", "/")).strip()
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)
    if not base or base in {".", ".."}:
        return "unnamed_file"
    return base


def extract_extension(filename: str) -> str:
    """Extract lowercase extension without leading dot."""
    clean = sanitize_filename(filename)
    _, ext = os.path.splitext(clean)
    return ext.lstrip(".").lower()


def validate_file_category(category: str) -> dict:
    """Validate that the requested category exists."""
    cat_key = (category or "").strip().lower()
    if cat_key not in FILE_CATEGORIES:
        raise UnsupportedFileExtensionError(
            f"Unknown file category '{category}'. Please select a valid category."
        )
    return FILE_CATEGORIES[cat_key]


def validate_file_for_category(filename: str, category: str) -> str:
    """Validate that a file's extension matches the selected category. Returns normalized extension."""
    cat_info = validate_file_category(category)
    ext = extract_extension(filename)
    allowed = cat_info["extensions"]

    if "*" in allowed:
        return ext

    if not ext or ext not in allowed:
        allowed_display = ", ".join(e.upper() for e in allowed)
        raise UnsupportedFileExtensionError(
            f"File '{sanitize_filename(filename)}' has extension '.{ext.upper() if ext else 'NONE'}', "
            f"which is not allowed in '{cat_info['label']}' (allowed: {allowed_display})."
        )
    return ext


def prepare_payload_files(
    files: Sequence[tuple[str, bytes]],
    category: Optional[str] = None,
) -> List[PayloadFile]:
    """Validate and normalize a batch of uploaded files."""
    if not files:
        raise EmptyFileSelectionError("Please select at least one file to hide.")

    prepared: List[PayloadFile] = []
    for raw_name, content in files:
        clean_name = sanitize_filename(raw_name)
        if category is not None:
            ext = validate_file_for_category(clean_name, category)
        else:
            ext = extract_extension(clean_name)
        prepared.append(PayloadFile(filename=clean_name, extension=ext, data=bytes(content)))

    return prepared


def create_zip_bundle(files: Sequence[PayloadFile]) -> bytes:
    """Package multiple extracted files into an in-memory ZIP archive, deduplicating colliding names."""
    buf = io.BytesIO()
    seen_names: Dict[str, int] = {}

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            arcname = sanitize_filename(item.filename)
            if arcname in seen_names:
                seen_names[arcname] += 1
                stem, ext = os.path.splitext(arcname)
                arcname = f"{stem}_{seen_names[arcname]}{ext}"
            else:
                seen_names[arcname] = 0
            zf.writestr(arcname, item.data)

    return buf.getvalue()
