"""Security-first file validation and magic-byte format detection."""
from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import olefile

from ..config import settings


class DocumentError(Exception):
    """Base error with HTTP status code and user-friendly message."""

    status_code: int = 400

    def __init__(self, message: str, code: str = "DOCUMENT_ERROR", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class UnsupportedFormatError(DocumentError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="UNSUPPORTED_FORMAT", status_code=415)


class CorruptedFileError(DocumentError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="CORRUPTED_FILE", status_code=422)


class PasswordProtectedError(DocumentError):
    def __init__(self, message: str = "This document is password-protected and cannot be opened.") -> None:
        super().__init__(message, code="PASSWORD_PROTECTED", status_code=422)


class EmptyFileError(DocumentError):
    def __init__(self, message: str = "The uploaded file is empty (0 bytes).") -> None:
        super().__init__(message, code="EMPTY_FILE", status_code=400)


class FileTooLargeError(DocumentError):
    def __init__(self, max_mb: int) -> None:
        super().__init__(
            f"File exceeds the maximum allowed size of {max_mb} MB.",
            code="FILE_TOO_LARGE",
            status_code=413,
        )


class SecurityValidationError(DocumentError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="SECURITY_VIOLATION", status_code=400)


@dataclass(frozen=True)
class DetectedFileInfo:
    format_id: str
    category: str
    mime_type: str
    extension: str
    has_macros: bool = False


FORMAT_CATALOG: dict[str, tuple[str, str]] = {
    "pdf": ("PDF", "application/pdf"),
    "doc": ("Microsoft Word", "application/msword"),
    "docx": ("Microsoft Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "ppt": ("Microsoft PowerPoint", "application/vnd.ms-powerpoint"),
    "pptx": ("Microsoft PowerPoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "xls": ("Microsoft Excel", "application/vnd.ms-excel"),
    "xlsx": ("Microsoft Excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "csv": ("Microsoft Excel", "text/csv"),
    "txt": ("Text Documents", "text/plain"),
    "rtf": ("Text Documents", "application/rtf"),
    "md": ("Text Documents", "text/markdown"),
    "odt": ("OpenDocument", "application/vnd.oasis.opendocument.text"),
    "ods": ("OpenDocument", "application/vnd.oasis.opendocument.spreadsheet"),
    "odp": ("OpenDocument", "application/vnd.oasis.opendocument.presentation"),
    "html": ("Web and Data Formats", "text/html"),
    "xml": ("Web and Data Formats", "application/xml"),
    "json": ("Web and Data Formats", "application/json"),
    "png": ("Images", "image/png"),
    "jpg": ("Images", "image/jpeg"),
    "jpeg": ("Images", "image/jpeg"),
    "webp": ("Images", "image/webp"),
    "tiff": ("Images", "image/tiff"),
}

SUPPORTED_EXTENSIONS = set(FORMAT_CATALOG.keys()) | {"htm", "tif"}

# Disallowed executable magic bytes
_BLOCKED_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x7fELF", "Linux ELF executable"),
    (b"MZ", "Windows PE/EXE executable"),
    (b"\xfe\xed\xfa\xce", "Mach-O executable"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit executable"),
    (b"\xca\xfe\xba\xbe", "Java class / Mach-O universal binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O little-endian executable"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit little-endian executable"),
]


def sanitize_filename(filename: str) -> str:
    """Prevent path traversal and strip unsafe characters."""
    if not filename:
        return "untitled"
    # Normalize slashes and keep only basename
    cleaned = filename.replace("\\", "/").split("/")[-1]
    cleaned = cleaned.replace("\x00", "").strip()
    # Remove any leading dots to avoid hidden files or '..'
    cleaned = cleaned.lstrip(".")
    cleaned = re.sub(r"[^A-Za-z0-9._\-\s()]", "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "untitled"
    return cleaned[:200]


def validate_safe_path(base_dir: Path, target_path: Path) -> Path:
    """Ensure target_path stays strictly within base_dir."""
    resolved_base = base_dir.resolve()
    resolved_target = target_path.resolve()
    try:
        resolved_target.relative_to(resolved_base)
    except ValueError as exc:
        raise SecurityValidationError("Invalid file path detected (path traversal blocked).") from exc
    return resolved_target


def _inspect_zip_format(data: bytes, ext: str) -> DetectedFileInfo:
    max_uncompressed = settings.max_zip_uncompressed_mb * 1024 * 1024
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > max_uncompressed:
                raise SecurityValidationError(
                    f"Archive uncompressed size exceeds safe limit ({settings.max_zip_uncompressed_mb} MB)."
                )
            names = set(zf.namelist())
            for name in names:
                if ".." in name or name.startswith("/") or name.startswith("\\"):
                    raise SecurityValidationError("Archive contains unsafe path traversal entries.")

            has_macros = any("vbaProject.bin" in n or n.endswith(".bin") and "vba" in n.lower() for n in names)

            # OpenDocument detection via mimetype entry
            if "mimetype" in names:
                try:
                    odt_mime = zf.read("mimetype").decode("ascii", errors="ignore").strip()
                except Exception:
                    odt_mime = ""
                if odt_mime == "application/vnd.oasis.opendocument.text":
                    return DetectedFileInfo("odt", *FORMAT_CATALOG["odt"], "odt", has_macros)
                if odt_mime == "application/vnd.oasis.opendocument.spreadsheet":
                    return DetectedFileInfo("ods", *FORMAT_CATALOG["ods"], "ods", has_macros)
                if odt_mime == "application/vnd.oasis.opendocument.presentation":
                    return DetectedFileInfo("odp", *FORMAT_CATALOG["odp"], "odp", has_macros)

            # OOXML detection
            if any(n.startswith("word/") for n in names) or "word/document.xml" in names:
                return DetectedFileInfo("docx", *FORMAT_CATALOG["docx"], "docx", has_macros)
            if any(n.startswith("ppt/") for n in names) or "ppt/presentation.xml" in names:
                return DetectedFileInfo("pptx", *FORMAT_CATALOG["pptx"], "pptx", has_macros)
            if any(n.startswith("xl/") for n in names) or "xl/workbook.xml" in names:
                return DetectedFileInfo("xlsx", *FORMAT_CATALOG["xlsx"], "xlsx", has_macros)

            # Fallback for ODF without mimetype file but with content.xml
            if "content.xml" in names and ext in {"odt", "ods", "odp"}:
                return DetectedFileInfo(ext, *FORMAT_CATALOG[ext], ext, has_macros)

            raise UnsupportedFormatError("ZIP archive is not a supported Office or OpenDocument file.")
    except zipfile.BadZipFile as exc:
        raise CorruptedFileError("File has a ZIP signature but is corrupted or truncated.") from exc


def _inspect_ole2_format(data: bytes, ext: str) -> DetectedFileInfo:
    try:
        with olefile.OleFileIO(io.BytesIO(data)) as ole:
            streams = ["/".join(entry) for entry in ole.listdir()]
            stream_set = set(streams)
            has_macros = any("Macros" in s or "VBA" in s for s in streams)

            if "EncryptedPackage" in stream_set or "EncryptionInfo" in stream_set:
                raise PasswordProtectedError("This Microsoft Office document is encrypted/password-protected.")

            if "WordDocument" in stream_set:
                return DetectedFileInfo("doc", *FORMAT_CATALOG["doc"], "doc", has_macros)
            if "PowerPoint Document" in stream_set or "Current User" in stream_set and ext == "ppt":
                return DetectedFileInfo("ppt", *FORMAT_CATALOG["ppt"], "ppt", has_macros)
            if "Workbook" in stream_set or "Book" in stream_set:
                return DetectedFileInfo("xls", *FORMAT_CATALOG["xls"], "xls", has_macros)

            if ext in {"doc", "ppt", "xls"}:
                return DetectedFileInfo(ext, *FORMAT_CATALOG[ext], ext, has_macros)
            raise UnsupportedFormatError("Unrecognized legacy OLE2 compound document format.")
    except PasswordProtectedError:
        raise
    except UnsupportedFormatError:
        raise
    except Exception as exc:
        raise CorruptedFileError(f"Corrupted legacy Office document: {exc}") from exc


def detect_and_validate(data: bytes, filename: str) -> DetectedFileInfo:
    """Validate size, block executables, and detect actual format from file signatures."""
    if not data:
        raise EmptyFileError("The uploaded file is empty (0 bytes).")
    if len(data) > settings.max_file_size_bytes:
        raise FileTooLargeError(settings.max_file_size_mb)

    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower().lstrip(".")
    if ext == "htm":
        ext = "html"
    elif ext == "tif":
        ext = "tiff"

    header = data[:32]

    # Block known executable binaries immediately
    for sig, label in _BLOCKED_SIGNATURES:
        if header.startswith(sig):
            raise SecurityValidationError(f"Blocked potentially dangerous file type ({label}).")

    # 1. PDF signature
    if header.startswith(b"%PDF-") or b"%PDF-" in data[:1024]:
        return DetectedFileInfo("pdf", *FORMAT_CATALOG["pdf"], "pdf")

    # 2. Image signatures
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return DetectedFileInfo("png", *FORMAT_CATALOG["png"], "png")
    if header.startswith(b"\xff\xd8\xff"):
        fmt = "jpeg" if ext == "jpeg" else "jpg"
        return DetectedFileInfo(fmt, *FORMAT_CATALOG[fmt], fmt)
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return DetectedFileInfo("webp", *FORMAT_CATALOG["webp"], "webp")
    if header.startswith(b"II*\x00") or header.startswith(b"MM\x00*"):
        return DetectedFileInfo("tiff", *FORMAT_CATALOG["tiff"], "tiff")

    # 3. ZIP-based documents (DOCX, PPTX, XLSX, ODT, ODS, ODP)
    if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06"):
        return _inspect_zip_format(data, ext)

    # 4. Legacy OLE2 documents (DOC, PPT, XLS, or encrypted OOXML)
    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return _inspect_ole2_format(data, ext)

    # 5. RTF signature
    stripped_start = data[:64].lstrip()
    if stripped_start.startswith(b"{\\rtf"):
        return DetectedFileInfo("rtf", *FORMAT_CATALOG["rtf"], "rtf")

    # 6. Text & structured formats (HTML, XML, JSON, CSV, MD, TXT)
    # Reject unknown binary payloads (contain NUL bytes outside UTF-16 BOM)
    is_utf16 = header.startswith(b"\xff\xfe") or header.startswith(b"\xfe\xff")
    if not is_utf16 and b"\x00" in data[:4096]:
        if ext in {"pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "odt", "ods", "odp", "png", "jpg", "jpeg", "webp", "tiff"}:
            raise CorruptedFileError(
                f"File '{safe_name}' does not match the valid binary signature for .{ext.upper()} and appears corrupted."
            )
        raise UnsupportedFormatError(f"Unsupported binary file format for '{safe_name}'.")

    # If the user claimed a binary format extension (e.g. .pdf, .docx, .png) but uploaded plain text
    binary_exts = {"pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "odt", "ods", "odp", "png", "jpg", "jpeg", "webp", "tiff"}
    if ext in binary_exts:
        raise CorruptedFileError(
            f"File '{safe_name}' has a .{ext.upper()} extension but its file signature is invalid or corrupted."
        )

    try:
        sample = data[:8192].decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        sample = data[:8192].decode("latin-1", errors="replace")

    sample_stripped = sample.lstrip()
    sample_lower = sample_stripped[:512].lower()

    if ext == "json" or (ext not in {"txt", "md", "csv", "html", "xml"} and sample_stripped.startswith(("{", "["))):
        try:
            json.loads(data.decode("utf-8", errors="strict"))
            return DetectedFileInfo("json", *FORMAT_CATALOG["json"], "json")
        except Exception as exc:
            if ext == "json":
                raise CorruptedFileError(f"Invalid JSON syntax: {exc}") from exc

    if ext == "html" or sample_lower.startswith("<!doctype html") or "<html" in sample_lower[:256]:
        return DetectedFileInfo("html", *FORMAT_CATALOG["html"], "html")

    if ext == "xml" or sample_lower.startswith("<?xml"):
        return DetectedFileInfo("xml", *FORMAT_CATALOG["xml"], "xml")

    if ext == "csv":
        return DetectedFileInfo("csv", *FORMAT_CATALOG["csv"], "csv")

    if ext == "md":
        return DetectedFileInfo("md", *FORMAT_CATALOG["md"], "md")

    if ext == "txt":
        return DetectedFileInfo("txt", *FORMAT_CATALOG["txt"], "txt")

    if ext == "rtf":
        raise CorruptedFileError("File has .rtf extension but lacks a valid RTF header.")

    raise UnsupportedFormatError(
        f"Unsupported file format '.{ext or 'unknown'}'. Please upload one of the supported document formats."
    )
