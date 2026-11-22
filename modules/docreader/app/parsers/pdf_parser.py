"""PDF parser supporting PyMuPDF (if installed) with full pypdf + pdfplumber + pypdfium2 engine."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pdfplumber
from pypdf import PdfReader
import pypdfium2 as pdfium

from ..config import settings
from ..security.file_validator import CorruptedFileError, PasswordProtectedError
from ..services.ocr_service import OCRError, ocr_service
from .base import (
    CancelCheck,
    DocumentParser,
    ParsedDocument,
    ParsedOutlineItem,
    ParsedPage,
    ParsedTable,
    ProgressCallback,
)

logger = logging.getLogger(__name__)


def render_pdf_page_png(file_path: Path, page_number: int, dpi: int = 150) -> bytes:
    """Render a 1-indexed PDF page to PNG bytes for lazy viewer/thumbnail loading."""
    pdf = pdfium.PdfDocument(str(file_path))
    try:
        if page_number < 1 or page_number > len(pdf):
            raise IndexError(f"Page {page_number} out of range (1..{len(pdf)}).")
        page = pdf[page_number - 1]
        scale = dpi / 72.0
        bitmap = page.render(scale=scale)
        pil_img = bitmap.to_pil()
        import io

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()


class PDFParser(DocumentParser):
    supported_formats = ("pdf",)

    def _extract_outline(self, reader: PdfReader) -> list[ParsedOutlineItem]:
        items: list[ParsedOutlineItem] = []

        def _walk(nodes: Any, level: int = 1) -> None:
            for node in nodes:
                if isinstance(node, list):
                    _walk(node, level + 1)
                else:
                    title = getattr(node, "title", None)
                    if title:
                        try:
                            page_idx = reader.get_destination_page_number(node) + 1
                        except Exception:
                            page_idx = 1
                        items.append(
                            ParsedOutlineItem(title=str(title).strip(), level=level, page_number=page_idx)
                        )

        try:
            raw_outline = reader.outline
            if raw_outline:
                _walk(raw_outline)
        except Exception:
            pass
        return items

    def parse(
        self,
        file_path: Path,
        format_id: str,
        *,
        ocr_lang: str = "eng",
        progress_cb: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
        force_ocr: bool = False,
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 10, "Opening PDF document")
        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            raise CorruptedFileError(f"Unable to open PDF file (corrupted or invalid): {exc}") from exc

        if reader.is_encrypted:
            # Try empty password (some PDFs are owner-locked only)
            try:
                res = reader.decrypt("")
                if res == 0:
                    raise PasswordProtectedError("This PDF is password-protected and requires a password to open.")
            except PasswordProtectedError:
                raise
            except Exception as exc:
                raise PasswordProtectedError("This PDF is password-protected and cannot be opened.") from exc

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise CorruptedFileError("PDF document contains 0 pages.")

        meta_raw = reader.metadata or {}
        metadata: dict[str, Any] = {
            "page_count": total_pages,
            "title": str(meta_raw.get("/Title", "") or "").strip() or None,
            "author": str(meta_raw.get("/Author", "") or "").strip() or None,
            "subject": str(meta_raw.get("/Subject", "") or "").strip() or None,
            "creator": str(meta_raw.get("/Creator", "") or "").strip() or None,
            "producer": str(meta_raw.get("/Producer", "") or "").strip() or None,
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}

        outline = self._extract_outline(reader)
        pages: list[ParsedPage] = []
        tables: list[ParsedTable] = []
        ocr_used = False
        table_counter = 0

        pdfium_doc: Optional[pdfium.PdfDocument] = None
        try:
            with pdfplumber.open(str(file_path)) as plumber_pdf:
                for idx, p_page in enumerate(plumber_pdf.pages, start=1):
                    self.check_cancel(is_cancelled)
                    pct = 15 + int((idx / total_pages) * 75)
                    self.report_progress(progress_cb, pct, f"Extracting PDF page {idx} of {total_pages}")

                    text = (p_page.extract_text(layout=False) or "").strip()
                    page_ocr = False

                    # Extract tables via pdfplumber
                    try:
                        raw_tables = p_page.extract_tables() or []
                        for raw_tbl in raw_tables:
                            cleaned_rows = [
                                [str(cell).strip() if cell is not None else "" for cell in row]
                                for row in raw_tbl
                                if row and any(cell is not None and str(cell).strip() for cell in row)
                            ]
                            if not cleaned_rows:
                                continue
                            headers = cleaned_rows[0]
                            body_rows = cleaned_rows[1:] if len(cleaned_rows) > 1 else []
                            tables.append(
                                ParsedTable(
                                    table_index=table_counter,
                                    page_number=idx,
                                    title=f"Page {idx} Table {table_counter + 1}",
                                    headers=headers,
                                    rows=body_rows,
                                )
                            )
                            table_counter += 1
                    except Exception as exc:
                        logger.debug("Table extraction skipped on page %d: %s", idx, exc)

                    # Automatic OCR for scanned PDF pages or when forced
                    if force_ocr or len(text) < settings.ocr_min_text_chars_per_page:
                        self.report_progress(progress_cb, pct, f"Running OCR on PDF page {idx} of {total_pages}")
                        try:
                            if pdfium_doc is None:
                                pdfium_doc = pdfium.PdfDocument(str(file_path))
                            f_page = pdfium_doc[idx - 1]
                            scale = settings.ocr_dpi / 72.0
                            pil_img = f_page.render(scale=scale).to_pil()
                            ocr_text = ocr_service.extract_text_from_pil(pil_img, lang=ocr_lang)
                            if ocr_text and (force_ocr or len(ocr_text) > len(text)):
                                text = ocr_text
                                page_ocr = True
                                ocr_used = True
                        except OCRError as exc:
                            logger.warning("OCR failed on PDF page %d: %s", idx, exc)
                        except Exception as exc:
                            logger.warning("Failed rendering PDF page %d for OCR: %s", idx, exc)

                    pages.append(
                        ParsedPage(
                            page_number=idx,
                            title=f"Page {idx}",
                            text=text,
                            ocr_applied=page_ocr,
                            has_image_preview=True,
                        )
                    )
        except (PasswordProtectedError, CorruptedFileError):
            raise
        except Exception as exc:
            raise CorruptedFileError(f"Failed while extracting PDF content: {exc}") from exc
        finally:
            if pdfium_doc is not None:
                try:
                    pdfium_doc.close()
                except Exception:
                    pass

        return ParsedDocument(
            pages=pages,
            tables=tables,
            outline=outline,
            metadata=metadata,
            ocr_used=ocr_used,
        )
