"""REST API routes for DOCREADER."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response

from ..config import settings
from ..database import db
from ..models import (
    AIQueryRequest,
    AIQueryResponse,
    DocumentDetail,
    DocumentSummary,
    OCRRunRequest,
    SearchResponse,
    StatsResponse,
)
from ..parsers.image_parser import render_image_frame_png
from ..parsers.pdf_parser import render_pdf_page_png
from ..parsers.registry import parser_registry
from ..security.file_validator import DocumentError, validate_safe_path
from ..services.ai_service import ai_service
from ..services.ocr_service import ocr_service
from ..services.pipeline import pipeline
from ..services.search_service import search_document

router = APIRouter(tags=["docreader"])


def _extract_paragraphs(full_text: str) -> list[str]:
    if not full_text.strip():
        return []
    parts = [p.strip() for p in re.split(r"\n\s*\n", full_text) if p.strip()]
    return parts if parts else [full_text.strip()]


def _safe_unlink(path_str: Optional[str]) -> None:
    if not path_str:
        return
    try:
        p = Path(path_str)
        if p.exists() and p.is_file():
            p.unlink()
    except Exception:
        pass


@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "max_file_size_mb": settings.max_file_size_mb,
        "temp_file_ttl_minutes": settings.temp_file_ttl_minutes,
        "ocr_languages": ocr_service.get_available_languages(),
        "external_ai_configured": bool(settings.openai_api_key or settings.gemini_api_key),
    }


@router.get("/formats")
def list_formats() -> dict:
    return {"formats": parser_registry.list_supported_formats()}


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    stats = db.get_stats()
    return StatsResponse(**stats, supported_formats=parser_registry.list_supported_formats())


@router.post("/documents/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    ocr_lang: Optional[str] = Form(default=None),
    async_mode: bool = Form(default=False),
) -> dict:
    """Upload one or more documents. Invalid files return structured errors without crashing."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    results = []
    errors = []

    for upload in files:
        filename = upload.filename or "untitled"
        try:
            # Stream-read with hard size cap to prevent memory exhaustion
            chunks: list[bytes] = []
            total = 0
            limit = settings.max_file_size_bytes + 1
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise DocumentError(
                        f"File '{filename}' exceeds the maximum allowed size of {settings.max_file_size_mb} MB.",
                        code="FILE_TOO_LARGE",
                        status_code=413,
                    )
                chunks.append(chunk)
            data = b"".join(chunks)

            doc = pipeline.ingest_upload(
                data,
                filename,
                ocr_lang=ocr_lang,
                run_sync=not async_mode,
            )
            if doc.get("status") == "failed":
                errors.append(
                    {
                        "filename": filename,
                        "document_id": doc["id"],
                        "code": "EXTRACTION_FAILED",
                        "message": doc.get("error_message") or "Document processing failed.",
                    }
                )
            else:
                results.append(doc)
        except DocumentError as exc:
            errors.append(
                {
                    "filename": filename,
                    "code": exc.code,
                    "message": exc.message,
                    "status_code": exc.status_code,
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "filename": filename,
                    "code": "UPLOAD_ERROR",
                    "message": f"Failed to process '{filename}': {exc}",
                    "status_code": 500,
                }
            )
        finally:
            await upload.close()

    # If a single file was uploaded and failed validation, return its proper HTTP error
    if len(files) == 1 and not results and errors:
        err = errors[0]
        raise HTTPException(
            status_code=int(err.get("status_code", 422)),
            detail={"code": err["code"], "message": err["message"], "filename": err["filename"]},
        )

    return {"documents": results, "errors": errors}


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(limit: int = Query(default=100, ge=1, le=500)) -> list[DocumentSummary]:
    return [DocumentSummary(**d) for d in db.list_documents(limit=limit)]


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: str) -> DocumentDetail:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    doc.pop("stored_path", None)
    doc["paragraphs"] = _extract_paragraphs(doc.get("full_text", ""))
    return DocumentDetail(**doc)


@router.get("/documents/{doc_id}/status")
def get_document_status(doc_id: str) -> dict:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {
        "id": doc["id"],
        "status": doc["status"],
        "progress": doc["progress"],
        "stage": doc["stage"],
        "error_message": doc["error_message"],
    }


@router.post("/documents/{doc_id}/cancel")
def cancel_document(doc_id: str) -> dict:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    cancelled = pipeline.request_cancel(doc_id)
    return {"id": doc_id, "cancelled": cancelled, "status": "cancelled" if cancelled else doc["status"]}


@router.get("/documents/{doc_id}/file")
def get_raw_file(doc_id: str) -> FileResponse:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    stored = doc.get("stored_path")
    if not stored or not Path(stored).exists():
        raise HTTPException(status_code=404, detail="Original temporary file has expired or been removed.")
    safe_path = validate_safe_path(settings.upload_dir, Path(stored))
    return FileResponse(path=str(safe_path), media_type=doc["mime_type"], filename=doc["filename"])


@router.get("/documents/{doc_id}/pages/{page_number}/image")
def get_page_image(
    doc_id: str,
    page_number: int,
    dpi: int = Query(default=144, ge=48, le=300),
    thumbnail: bool = Query(default=False),
) -> Response:
    """Lazy-load rendered PNG for a PDF page or image frame."""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    stored = doc.get("stored_path")
    if not stored or not Path(stored).exists():
        raise HTTPException(status_code=404, detail="Original temporary file is no longer available.")
    safe_path = validate_safe_path(settings.upload_dir, Path(stored))
    fmt = doc["detected_format"]

    try:
        if fmt == "pdf":
            target_dpi = 64 if thumbnail else dpi
            png_bytes = render_pdf_page_png(safe_path, page_number, dpi=target_dpi)
        elif fmt in ("png", "jpg", "jpeg", "webp", "tiff"):
            png_bytes = render_image_frame_png(safe_path, page_number)
        else:
            raise HTTPException(status_code=400, detail=f"Image rendering is not applicable for .{fmt} files.")
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render page image: {exc}") from exc

    return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


@router.get("/documents/{doc_id}/text")
def download_extracted_text(doc_id: str) -> PlainTextResponse:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    stem = Path(doc["filename"]).stem or "document"
    return PlainTextResponse(
        content=doc.get("full_text", ""),
        headers={"Content-Disposition": f'attachment; filename="{stem}_extracted.txt"'},
    )


@router.post("/documents/{doc_id}/ocr", response_model=DocumentDetail)
def rerun_ocr(doc_id: str, req: OCRRunRequest) -> DocumentDetail:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    stored = doc.get("stored_path")
    if not stored or not Path(stored).exists():
        raise HTTPException(status_code=404, detail="Original file has expired; re-upload to run OCR.")
    safe_path = validate_safe_path(settings.upload_dir, Path(stored))
    pipeline.process_document(
        doc_id,
        doc["detected_format"],
        doc["category"],
        doc["mime_type"],
        safe_path,
        ocr_lang=req.language,
        force_ocr=req.force_all_pages,
    )
    updated = db.get_document(doc_id)
    assert updated is not None
    updated.pop("stored_path", None)
    updated["paragraphs"] = _extract_paragraphs(updated.get("full_text", ""))
    return DocumentDetail(**updated)


@router.get("/documents/{doc_id}/search", response_model=SearchResponse)
def search_in_document(
    doc_id: str,
    q: str = Query(..., min_length=1, max_length=500),
    case_sensitive: bool = Query(default=False),
) -> SearchResponse:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return search_document(doc, q, case_sensitive=case_sensitive)


@router.post("/documents/{doc_id}/ai", response_model=AIQueryResponse)
async def query_ai_assistant(doc_id: str, req: AIQueryRequest) -> AIQueryResponse:
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    chunks = db.get_chunks(doc_id)
    try:
        return await ai_service.query(doc, chunks, req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict:
    stored = db.delete_document(doc_id)
    if stored is None:
        # Check if doc existed with NULL stored_path
        raise HTTPException(status_code=404, detail="Document not found.")
    _safe_unlink(stored)
    return {"deleted": True, "id": doc_id}


@router.delete("/documents")
def clear_all_documents() -> dict:
    paths = db.clear_all()
    for p in paths:
        _safe_unlink(p)
    return {"cleared": True, "removed_files": len(paths)}
