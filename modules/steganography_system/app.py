"""FastAPI backend for the Universal Image Steganography Application."""

from __future__ import annotations

import base64
import os
import secrets
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from modules import extraction_engine, file_manager, image_handler, steganography_engine
from modules.exceptions import (
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
from modules.file_manager import PayloadFile
from modules.image_handler import format_bytes, format_capacity_all_units

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
COMPONENTS_DIR = FRONTEND_DIR / "components"
STATIC_DIR = FRONTEND_DIR / "static"

MAX_CACHE_ITEMS = 20
CACHE_TTL_SECONDS = 3600  # 1 hour

app = FastAPI(
    title="Universal Image Steganography",
    description="Hide any digital file inside ordinary PNG/JPEG images using RGB LSB steganography.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=[str(TEMPLATES_DIR), str(COMPONENTS_DIR)])

# Bounded in-memory caches for download tokens (never written to disk in plaintext)
_encoded_store: "OrderedDict[str, dict]" = OrderedDict()
_extracted_store: "OrderedDict[str, dict]" = OrderedDict()


def _prune_cache(store: "OrderedDict[str, dict]") -> None:
    now = time.time()
    expired = [k for k, v in store.items() if now - v["created_at"] > CACHE_TTL_SECONDS]
    for key in expired:
        store.pop(key, None)
    while len(store) > MAX_CACHE_ITEMS:
        store.popitem(last=False)


def _content_disposition(filename: str) -> str:
    safe_ascii = "".join(c if 32 <= ord(c) < 127 and c not in {'"', "\\"} else "_" for c in filename)
    encoded_utf8 = quote(filename, safe="")
    return f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded_utf8}"


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


@app.exception_handler(MemoryError)
async def memory_error_handler(_request: Request, _exc: MemoryError) -> JSONResponse:
    return JSONResponse(
        status_code=507,
        content={
            "ok": False,
            "error_type": "MemoryError",
            "message": "Insufficient memory to complete this operation. Try a smaller image or smaller files.",
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error_type": "UnexpectedError",
            "message": "An unexpected error occurred while processing your request. Please verify your files and try again.",
        },
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main Universal Image Steganography web interface."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "categories": list(file_manager.FILE_CATEGORIES.values()),
        },
    )


@app.get("/api/categories")
async def get_categories():
    """Return all supported file categories and their allowed extensions."""
    return {
        "ok": True,
        "categories": list(file_manager.FILE_CATEGORIES.values()),
    }


@app.post("/api/analyze-image")
async def analyze_image(image: UploadFile = File(...)):
    """Validate an uploaded container image and compute its RGB LSB storage capacity."""
    image_bytes = await image.read()
    _, info = image_handler.load_and_prepare_container(
        image_bytes, filename=image.filename or "image.png", allow_jpeg=True
    )
    return {
        "ok": True,
        "image": info.to_dict(),
    }


@app.post("/api/analyze-capacity")
async def analyze_capacity(
    image: UploadFile = File(...),
    files: List[UploadFile] = File(default=[]),
    category: str = Form(...),
    use_encryption: bool = Form(default=False),
):
    """Compute exact storage capacity vs. required payload size before encoding."""
    image_bytes = await image.read()
    payload_pairs = []
    for upload in files:
        content = await upload.read()
        payload_pairs.append((upload.filename or "file", content))

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


@app.post("/api/encode")
async def encode_endpoint(
    image: UploadFile = File(...),
    files: List[UploadFile] = File(default=[]),
    category: str = Form(...),
    use_encryption: bool = Form(default=False),
    password: Optional[str] = Form(default=None),
):
    """Encode one or more files into a lossless PNG container image."""
    image_bytes = await image.read()
    payload_pairs = []
    for upload in files:
        content = await upload.read()
        payload_pairs.append((upload.filename or "file", content))

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

    encoded_preview_b64 = base64.b64encode(result.encoded_png_bytes).decode("ascii")

    return {
        "ok": True,
        "job_id": job_id,
        "download_url": f"/api/download/encoded/{job_id}",
        "download_filename": download_filename,
        "encoded_preview_data_url": f"data:image/png;base64,{encoded_preview_b64}",
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


@app.get("/api/download/encoded/{job_id}")
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


@app.post("/api/inspect")
async def inspect_endpoint(image: UploadFile = File(...)):
    """Inspect an uploaded PNG to detect whether it contains a payload from this application."""
    image_bytes = await image.read()
    result = extraction_engine.inspect_encoded_image(
        image_bytes=image_bytes,
        image_filename=image.filename or "encoded.png",
    )
    return {
        "ok": True,
        **result.to_dict(),
    }


@app.post("/api/extract")
async def extract_endpoint(
    image: UploadFile = File(...),
    password: Optional[str] = Form(default=None),
):
    """Extract and verify hidden files from an encoded PNG image."""
    image_bytes = await image.read()
    result = extraction_engine.extract_files_from_image(
        image_bytes=image_bytes,
        image_filename=image.filename or "encoded.png",
        password=password or None,
    )

    _prune_cache(_extracted_store)
    session_id = secrets.token_urlsafe(16)
    _extracted_store[session_id] = {
        "created_at": time.time(),
        "files": result.files,
    }

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
                "download_url": f"/api/download/extracted/{session_id}/{idx}",
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
        "zip_download_url": f"/api/download/extracted/{session_id}/all.zip"
        if len(result.files) > 1
        else None,
    }


@app.get("/api/download/extracted/{session_id}/all.zip")
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


@app.get("/api/download/extracted/{session_id}/{file_index}")
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
