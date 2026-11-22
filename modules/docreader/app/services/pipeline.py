"""Universal 9-step document processing pipeline with progress & cancellation support."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from ..config import settings
from ..database import db
from ..parsers.base import ProcessingCancelledError
from ..parsers.pdf_parser import PDFParser
from ..parsers.registry import parser_registry
from ..security.file_validator import (
    DocumentError,
    detect_and_validate,
    sanitize_filename,
    validate_safe_path,
)
from .ai_service import chunk_pages

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """Manages document ingestion, validation, parsing, OCR, chunking, and cancellation."""

    def __init__(self) -> None:
        self._cancel_flags: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def request_cancel(self, doc_id: str) -> bool:
        with self._lock:
            ev = self._cancel_flags.get(doc_id)
            if ev:
                ev.set()
                db.update_status(doc_id, status="cancelled", stage="Cancelled by user")
                return True
        return False

    def _is_cancelled(self, doc_id: str) -> bool:
        with self._lock:
            ev = self._cancel_flags.get(doc_id)
            return bool(ev and ev.is_set())

    def ingest_upload(
        self,
        data: bytes,
        original_filename: str,
        *,
        ocr_lang: Optional[str] = None,
        run_sync: bool = True,
    ) -> dict:
        """Steps 1–3: Validate size & signature, detect actual format, save safely, and process."""
        safe_name = sanitize_filename(original_filename)
        info = detect_and_validate(data, safe_name)

        doc_id = uuid.uuid4().hex
        settings.ensure_dirs()
        stored_path = validate_safe_path(settings.upload_dir, settings.upload_dir / f"{doc_id}.{info.extension}")
        stored_path.write_bytes(data)

        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=settings.temp_file_ttl_minutes)

        db.create_document(
            {
                "id": doc_id,
                "filename": safe_name,
                "stored_path": str(stored_path),
                "detected_format": info.format_id,
                "category": info.category,
                "mime_type": info.mime_type,
                "file_size": len(data),
                "status": "queued",
                "progress": 5,
                "stage": "Validated file signature",
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
            }
        )

        with self._lock:
            self._cancel_flags[doc_id] = threading.Event()

        if run_sync:
            self.process_document(doc_id, info.format_id, info.category, info.mime_type, stored_path, ocr_lang=ocr_lang, has_macros=info.has_macros)
        else:
            thread = threading.Thread(
                target=self.process_document,
                args=(doc_id, info.format_id, info.category, info.mime_type, stored_path),
                kwargs={"ocr_lang": ocr_lang, "has_macros": info.has_macros},
                daemon=True,
            )
            thread.start()

        doc = db.get_document(doc_id)
        return doc or {"id": doc_id, "status": "failed"}

    def process_document(
        self,
        doc_id: str,
        format_id: str,
        category: str,
        mime_type: str,
        stored_path: Path,
        *,
        ocr_lang: Optional[str] = None,
        has_macros: bool = False,
        force_ocr: bool = False,
    ) -> None:
        """Steps 4–9: Select parser, extract content, run OCR if required, chunk, and persist."""
        try:
            db.update_status(doc_id, status="processing", progress=10, stage=f"Selecting {format_id.upper()} parser")
            parser = parser_registry.get(format_id)

            def _progress(pct: int, stage: str) -> None:
                db.update_status(doc_id, status="processing", progress=max(10, min(95, pct)), stage=stage)

            def _cancel_check() -> bool:
                return self._is_cancelled(doc_id)

            if isinstance(parser, PDFParser) and force_ocr:
                parsed = parser.parse(
                    stored_path,
                    format_id,
                    ocr_lang=ocr_lang or settings.ocr_default_lang,
                    progress_cb=_progress,
                    is_cancelled=_cancel_check,
                    force_ocr=True,
                )
            else:
                parsed = parser.parse(
                    stored_path,
                    format_id,
                    ocr_lang=ocr_lang or settings.ocr_default_lang,
                    progress_cb=_progress,
                    is_cancelled=_cancel_check,
                )

            if _cancel_check():
                raise ProcessingCancelledError("Processing cancelled.")

            if has_macros:
                parsed.metadata["security_notice"] = "Macros detected in archive and safely ignored (never executed)."

            db.update_status(doc_id, status="processing", progress=96, stage="Indexing for search and AI")
            pages_dicts = [p.to_dict() for p in parsed.pages]
            tables_dicts = [t.to_dict() for t in parsed.tables]
            outline_dicts = [o.to_dict() for o in parsed.outline]
            chunks = chunk_pages(pages_dicts, settings.chunk_size_chars, settings.chunk_overlap_chars)

            db.save_parsed_content(
                doc_id,
                detected_format=format_id,
                category=category,
                mime_type=mime_type,
                pages=pages_dicts,
                tables=tables_dicts,
                outline=outline_dicts,
                metadata=parsed.metadata,
                full_text=parsed.full_text,
                chunks=chunks,
                ocr_used=parsed.ocr_used,
            )
        except ProcessingCancelledError:
            db.update_status(doc_id, status="cancelled", stage="Cancelled by user", error_message="Processing cancelled.")
        except DocumentError as exc:
            db.update_status(doc_id, status="failed", progress=100, stage="Failed", error_message=exc.message)
        except Exception as exc:
            logger.exception("Unexpected error processing document %s", doc_id)
            db.update_status(
                doc_id,
                status="failed",
                progress=100,
                stage="Failed",
                error_message=f"Extraction failed: {exc}",
            )
        finally:
            with self._lock:
                self._cancel_flags.pop(doc_id, None)


pipeline = ProcessingPipeline()
