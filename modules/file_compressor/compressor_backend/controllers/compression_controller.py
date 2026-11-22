"""FastAPI controller handlers for file upload, compression, status, download, and cleanup."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ..middleware.file_validation import (
    MAX_GLOBAL_FILE_SIZE_BYTES,
    SUPPORTED_FORMATS,
    sanitize_filename,
    validate_uploaded_file,
)
from ..services.compression_service import (
    delete_job,
    get_job,
    get_job_status,
    process_compression_job,
    register_uploaded_file,
)
from ..utils.file_cleanup import cleanup_job_directory, create_job_directory

MIME_MAP = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "zip": "application/zip",
}


async def handle_upload(file: UploadFile) -> JSONResponse:
    job_id, job_dir = create_job_directory()
    safe_name = sanitize_filename(file.filename)
    dest_path = job_dir / f"original_{safe_name}"

    try:
        written = 0
        with dest_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_GLOBAL_FILE_SIZE_BYTES:
                    cleanup_job_directory(job_dir)
                    return JSONResponse(
                        status_code=413,
                        content={
                            "success": False,
                            "error": f"File exceeds maximum allowed limit of {MAX_GLOBAL_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
                        },
                    )
                out.write(chunk)

        validation = validate_uploaded_file(dest_path, file.filename or safe_name)
        if not validation["valid"]:
            cleanup_job_directory(job_dir)
            return JSONResponse(status_code=400, content={"success": False, "error": validation["error"]})

        job = register_uploaded_file(
            job_id=job_id,
            file_path=dest_path,
            original_name=validation["sanitizedName"],
            fmt=validation["format"],
            category=validation["category"],
            size=validation["size"],
        )
        return JSONResponse(status_code=201, content={"success": True, "job": job})
    except Exception as exc:
        cleanup_job_directory(job_dir)
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})


def handle_compress(payload: dict[str, Any], async_mode: bool = False) -> JSONResponse:
    job_id = payload.get("jobId")
    if not job_id:
        return JSONResponse(status_code=400, content={"success": False, "error": "Missing jobId."})

    existing = get_job(job_id)
    if not existing:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Job not found or temporary file has already been cleaned up."},
        )

    raw_target = payload.get("targetSizeBytes")
    parsed_target: int | None = None
    if raw_target is not None and raw_target != "":
        try:
            parsed_target = int(float(raw_target))
        except (TypeError, ValueError):
            return JSONResponse(status_code=400, content={"success": False, "error": "Target size must be a positive number."})
        if parsed_target <= 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Target size must be a positive number."})
        if parsed_target >= existing["originalSize"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Target size must be smaller than the original file size."},
            )

    settings = payload.get("settings") or {}

    if async_mode:
        def _runner() -> None:
            try:
                process_compression_job(job_id, target_size_bytes=parsed_target, settings=settings)
            except Exception:
                pass

        threading.Thread(target=_runner, daemon=True).start()
        return JSONResponse(status_code=202, content={"success": True, "job": get_job_status(job_id)})

    try:
        completed = process_compression_job(job_id, target_size_bytes=parsed_target, settings=settings)
        return JSONResponse(status_code=200, content={"success": True, "job": completed})
    except Exception as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})


def handle_status(job_id: str) -> JSONResponse:
    status = get_job_status(job_id)
    if not status:
        return JSONResponse(status_code=404, content={"success": False, "error": "Compression job not found."})
    return JSONResponse(status_code=200, content={"success": True, "job": status})


def handle_download(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if not job or job.get("status") != "completed" or not job.get("outputPath"):
        raise HTTPException(status_code=404, detail="Compressed file is not ready or has been deleted.")
    out_path = Path(job["outputPath"])
    if not out_path.is_file():
        raise HTTPException(status_code=404, detail="Compressed file has been deleted.")
    return FileResponse(
        path=str(out_path),
        media_type=MIME_MAP.get(job["format"], "application/octet-stream"),
        filename=Path(job["outputName"]).name,
        headers={"X-Content-Type-Options": "nosniff"},
    )


def handle_cleanup(job_id: str) -> JSONResponse:
    removed = delete_job(job_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "cleaned": removed,
            "message": "Temporary files deleted successfully." if removed else "No active temporary files found.",
        },
    )


def handle_health() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status": "ok",
            "runtime": "python-fastapi",
            "supportedFormats": list(SUPPORTED_FORMATS.keys()),
        },
    )
