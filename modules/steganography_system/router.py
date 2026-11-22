"""CITADEL FastAPI router adapter for Module 01: Steganography System.

Wraps the existing Universal Image Steganography backend engines without
rewriting or duplicating any steganography, compression, encryption, or
integrity-verification logic.
"""

from __future__ import annotations

import base64
import os
import secrets
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response

# Ensure the original steganography module package resolves cleanly
STEG_ROOT = Path(__file__).resolve().parent
if str(STEG_ROOT) not in sys.path:
    sys.path.insert(0, str(STEG_ROOT))

from modules import extraction_engine, file_manager, image_handler, steganography_engine  # noqa: E402
from modules.exceptions import (  # noqa: E402
    CapacityExceededError,
    CompressionError,
    CorruptedPayloadError,
    DecryptionError,
    EmptyFileSelectionError,
    EncryptionError,
    InvalidImageError,
    NoPayloadError,
    PasswordRequiredError,
    SteganographyError,
    UnsupportedFileExtensionError,
    UnsupportedImageFormatError,
)
from modules.file_manager import PayloadFile  # noqa: E402
from modules.image_handler import (  # noqa: E402
    format_bytes,
    format_capacity_all_units,
    make_preview_thumbnail_bytes,
)

from backend.core.config import (  # noqa: E402
    MAX_FILES_PER_REQUEST,
    MAX_IMAGE_UPLOAD_BYTES,
    MAX_PAYLOAD_TOTAL_BYTES,
)

MAX_CACHE_ITEMS = 12
MAX_INSPECT_CACHE_ITEMS = 4
CACHE_TTL_SECONDS = 3600  # 1 hour
INSPECT_TTL_SECONDS = 900  # 15 minutes
_READ_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB streaming chunks

# Bounded in-memory caches (never written to disk in plaintext)
_encoded_store: "OrderedDict[str, dict]" = OrderedDict()
_extracted_store: "OrderedDict[str, dict]" = OrderedDict()
_inspect_store: "OrderedDict[str, dict]" = OrderedDict()


def _prune_cache(store: "OrderedDict[str, dict]", max_items: int = MAX_CACHE_ITEMS, ttl: int = CACHE_TTL_SECONDS) -> None:
    now = time.time()
    expired = [k for k, v in store.items() if now - v["created_at"] > ttl]
    for key in expired:
        store.pop(key, None)
    while len(store) > max_items:
        store.popitem(last=False)


def _content_disposition(filename: str) -> str:
    safe_ascii = "".join(c if 32 <= ord(c) < 127 and c not in {'"', "\\"} else "_" for c in filename)
    encoded_utf8 = quote(filename, safe="")
    return f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded_utf8}"


def _api_base_from_request(request: Request) -> str:
    """Return the matched API prefix (e.g. '/api/modules/steganography' or '/api')."""
    path = request.url.path
    for suffix in ("/encode", "/extract"):
        if path.endswith(suffix):
            return path[: -len(suffix)]
    return "/api/modules/steganography"


async def _read_image_bounded(upload: UploadFile) -> bytes:
    """Stream-read an uploaded image in chunks up to MAX_IMAGE_UPLOAD_BYTES."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_IMAGE_UPLOAD_BYTES:
            raise CapacityExceededError(
                f"Container image exceeds the maximum allowed upload size of {format_bytes(MAX_IMAGE_UPLOAD_BYTES)}."
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _read_payload_files_bounded(files: List[UploadFile]) -> list[tuple[str, bytes]]:
    if len(files) > MAX_FILES_PER_REQUEST:
        raise EmptyFileSelectionError(
            f"Too many files selected. Please upload at most {MAX_FILES_PER_REQUEST} files at once."
        )
    payload_pairs: list[tuple[str, bytes]] = []
    total_read = 0
    for upload in files:
        file_chunks: list[bytes] = []
        while True:
            chunk = await upload.read(_READ_CHUNK_SIZE)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > MAX_PAYLOAD_TOTAL_BYTES:
                raise CapacityExceededError(
                    f"Selected files exceed the maximum allowed total upload size of {format_bytes(MAX_PAYLOAD_TOTAL_BYTES)}."
                )
            file_chunks.append(chunk)
        payload_pairs.append((upload.filename or "file", b"".join(file_chunks)))
    return payload_pairs


def register_exception_handlers(app) -> None:
    """Register SteganographyError handler on the parent CITADEL FastAPI app."""

    @app.exception_handler(SteganographyError)
    async def steganography_error_handler(_request: Request, exc: SteganographyError) -> JSONResponse:
        status_map = {
            InvalidImageError: 400,
            UnsupportedImageFormatError: 400,
            UnsupportedFileExtensionError: 400,
            EmptyFileSelectionError: 400,
            CapacityExceededError: 413,
            EncryptionError: 400,
            PasswordRequiredError: 401,
            DecryptionError: 401,
            NoPayloadError: 404,
            CorruptedPayloadError: 422,
            CompressionError: 422,
        }
        status_code = status_map.get(type(exc), 400)
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        )


def create_router() -> APIRouter:
    """Build and return the Steganography System APIRouter."""
    router = APIRouter()

    @router.get("/health")
    async def module_health():
        return {
            "ok": True,
            "module_id": "steganography-system",
            "status": "Available",
        }

    @router.get("/categories")
    async def get_categories():
        """Return all supported file categories and their allowed extensions."""
        return {
            "ok": True,
            "categories": list(file_manager.FILE_CATEGORIES.values()),
        }

    @router.post("/analyze-image")
    async def analyze_image(image: UploadFile = File(...)):
        """Validate an uploaded container image and compute its RGB LSB storage capacity."""
        image_bytes = await _read_image_bounded(image)
        _, info = image_handler.load_and_prepare_container(
            image_bytes, filename=image.filename or "image.png", allow_jpeg=True
        )
        return {
            "ok": True,
            "image": info.to_dict(),
        }

    @router.post("/analyze-capacity")
    async def analyze_capacity(
        image: UploadFile = File(...),
        files: List[UploadFile] = File(default=[]),
        category: str = Form(...),
        use_encryption: bool = Form(default=False),
    ):
        """Compute exact storage capacity vs. required payload size before encoding."""
        image_bytes = await _read_image_bounded(image)
        payload_pairs = await _read_payload_files_bounded(files)

        image_info, analysis = steganography_engine.analyze_storage_capacity(
            image_bytes=image_bytes,
            image_filename=image.filename or "image.png",
            files=payload_pairs,
            category=category,
            use_encryption=use_encryption,
        )
        return {
            "ok": True,
            "image": image_info.to_dict(),
            "storage": analysis.to_dict(),
        }

    @router.post("/encode")
    async def encode_endpoint(
        request: Request,
        image: UploadFile = File(...),
        files: List[UploadFile] = File(default=[]),
        category: str = Form(...),
        use_encryption: bool = Form(default=False),
        password: Optional[str] = Form(default=None),
    ):
        """Encode one or more files into a lossless PNG container image."""
        image_bytes = await _read_image_bounded(image)
        payload_pairs = await _read_payload_files_bounded(files)

        effective_password = None
        if use_encryption:
            if not password:
                raise EncryptionError("Please enter a password when password protection is enabled.")
            effective_password = password

        result = steganography_engine.encode_files_into_image(
            image_bytes=image_bytes,
            image_filename=image.filename or "image.png",
            files=payload_pairs,
            category=category,
            password=effective_password,
        )

        stem = os.path.splitext(file_manager.sanitize_filename(result.image_info.filename))[0]
        download_filename = f"{stem}_stego.png"

        _prune_cache(_encoded_store)
        job_id = secrets.token_urlsafe(16)
        _encoded_store[job_id] = {
            "created_at": time.time(),
            "filename": download_filename,
            "data": result.encoded_png_bytes,
        }

        preview_bytes, preview_mime = make_preview_thumbnail_bytes(result.encoded_png_bytes)
        encoded_preview_b64 = base64.b64encode(preview_bytes).decode("ascii")
        api_base = _api_base_from_request(request)

        return {
            "ok": True,
            "job_id": job_id,
            "download_url": f"{api_base}/download/encoded/{job_id}",
            "download_filename": download_filename,
            "encoded_preview_data_url": f"data:{preview_mime};base64,{encoded_preview_b64}",
            "original_image": result.image_info.to_dict(),
            "encoded_size_bytes": result.encoded_size_bytes,
            "encoded_size_formatted": format_bytes(result.encoded_size_bytes),
            "embedded_payload_bytes": result.embedded_payload_bytes,
            "embedded_payload_formatted": format_bytes(result.embedded_payload_bytes),
            "raw_files_size_bytes": result.raw_files_size_bytes,
            "raw_files_size_formatted": format_bytes(result.raw_files_size_bytes),
            "file_count": result.file_count,
            "filenames": result.filenames,
            "encrypted": result.encrypted,
            "algorithm": result.algorithm,
            "steps_completed": result.steps_completed,
        }

    @router.get("/download/encoded/{job_id}")
    async def download_encoded(job_id: str):
        """Download the generated steganographic PNG image."""
        _prune_cache(_encoded_store)
        item = _encoded_store.get(job_id)
        if not item:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error_type": "NotFound",
                    "message": "The encoded image session has expired. Please generate the image again.",
                },
            )
        return Response(
            content=item["data"],
            media_type="image/png",
            headers={"Content-Disposition": _content_disposition(item["filename"])},
        )

    @router.post("/inspect")
    async def inspect_endpoint(image: UploadFile = File(...)):
        """Inspect an uploaded PNG to detect whether it contains a payload from this application."""
        image_bytes = await _read_image_bounded(image)
        filename = image.filename or "encoded.png"
        result = extraction_engine.inspect_encoded_image(
            image_bytes=image_bytes,
            image_filename=filename,
        )

        inspect_token = None
        if result.has_payload:
            _prune_cache(_inspect_store, max_items=MAX_INSPECT_CACHE_ITEMS, ttl=INSPECT_TTL_SECONDS)
            inspect_token = secrets.token_urlsafe(16)
            _inspect_store[inspect_token] = {
                "created_at": time.time(),
                "filename": filename,
                "data": image_bytes,
            }

        return {
            "ok": True,
            "inspect_token": inspect_token,
            **result.to_dict(),
        }

    @router.post("/extract")
    async def extract_endpoint(
        request: Request,
        image: Optional[UploadFile] = File(default=None),
        inspect_token: Optional[str] = Form(default=None),
        password: Optional[str] = Form(default=None),
    ):
        """Extract and verify hidden files from an encoded PNG image."""
        image_bytes: Optional[bytes] = None
        filename = "encoded.png"

        if inspect_token:
            _prune_cache(_inspect_store, max_items=MAX_INSPECT_CACHE_ITEMS, ttl=INSPECT_TTL_SECONDS)
            cached = _inspect_store.get(inspect_token)
            if cached:
                image_bytes = cached["data"]
                filename = cached["filename"]

        if image_bytes is None:
            if image is None:
                raise InvalidImageError("Please upload an encoded PNG image to extract.")
            image_bytes = await _read_image_bounded(image)
            filename = image.filename or "encoded.png"

        result = extraction_engine.extract_files_from_image(
            image_bytes=image_bytes,
            image_filename=filename,
            password=password or None,
        )

        _prune_cache(_extracted_store)
        session_id = secrets.token_urlsafe(16)
        _extracted_store[session_id] = {
            "created_at": time.time(),
            "files": result.files,
        }

        api_base = _api_base_from_request(request)
        files_meta = []
        for idx, f in enumerate(result.files):
            files_meta.append(
                {
                    "index": idx,
                    "filename": f.filename,
                    "extension": f.extension,
                    "size_bytes": f.size,
                    "size_formatted": format_bytes(f.size),
                    "size_units": format_capacity_all_units(f.size),
                    "download_url": f"{api_base}/download/extracted/{session_id}/{idx}",
                }
            )

        return {
            "ok": True,
            "session_id": session_id,
            "version": result.version,
            "is_compressed": result.is_compressed,
            "is_encrypted": result.is_encrypted,
            "overall_sha256": result.overall_sha256_hex,
            "file_count": len(result.files),
            "total_size_bytes": sum(f.size for f in result.files),
            "total_size_formatted": format_bytes(sum(f.size for f in result.files)),
            "files": files_meta,
            "zip_download_url": f"{api_base}/download/extracted/{session_id}/all.zip"
            if len(result.files) > 1
            else None,
        }

    @router.get("/download/extracted/{session_id}/all.zip")
    async def download_extracted_zip(session_id: str):
        """Download all extracted files packaged as a single ZIP archive."""
        _prune_cache(_extracted_store)
        session = _extracted_store.get(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error_type": "NotFound",
                    "message": "The extraction session has expired. Please upload the encoded image again.",
                },
            )
        files: List[PayloadFile] = session["files"]
        zip_bytes = file_manager.create_zip_bundle(files)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": _content_disposition("extracted_files.zip")},
        )

    @router.get("/download/extracted/{session_id}/{file_index}")
    async def download_extracted_file(session_id: str, file_index: int):
        """Download a single extracted file with its original filename and extension."""
        _prune_cache(_extracted_store)
        session = _extracted_store.get(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error_type": "NotFound",
                    "message": "The extraction session has expired. Please upload the encoded image again.",
                },
            )
        files: List[PayloadFile] = session["files"]
        if file_index < 0 or file_index >= len(files):
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error_type": "NotFound",
                    "message": "Requested file index was not found.",
                },
            )
        target = files[file_index]
        return Response(
            content=target.data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": _content_disposition(target.filename)},
        )

    return router
