"""Image parser supporting PNG, JPG, JPEG, WEBP, and multi-frame TIFF with OCR."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageSequence

from ..security.file_validator import CorruptedFileError
from ..services.ocr_service import OCRError, ocr_service
from .base import (
    CancelCheck,
    DocumentParser,
    ParsedDocument,
    ParsedPage,
    ProgressCallback,
)


def render_image_frame_png(file_path: Path, page_number: int = 1) -> bytes:
    """Return PNG bytes for a 1-indexed image frame (supports multi-page TIFF & WEBP)."""
    with Image.open(file_path) as img:
        n_frames = getattr(img, "n_frames", 1)
        frame_idx = max(0, min(page_number - 1, n_frames - 1))
        if n_frames > 1:
            img.seek(frame_idx)
        rgb = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img.copy()
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        return buf.getvalue()


class ImageParser(DocumentParser):
    supported_formats = ("png", "jpg", "jpeg", "webp", "tiff")

    def parse(
        self,
        file_path: Path,
        format_id: str,
        *,
        ocr_lang: str = "eng",
        progress_cb: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 15, f"Loading {format_id.upper()} image")
        try:
            with Image.open(file_path) as img:
                img.verify()
        except Exception as exc:
            raise CorruptedFileError(f"Corrupted or unreadable image file: {exc}") from exc

        pages: list[ParsedPage] = []
        ocr_used = False
        metadata: dict[str, Any] = {}

        with Image.open(file_path) as img:
            n_frames = getattr(img, "n_frames", 1)
            metadata = {
                "width": img.width,
                "height": img.height,
                "mode": img.mode,
                "image_format": img.format,
                "frames": n_frames,
            }

            for idx, frame in enumerate(ImageSequence.Iterator(img), start=1):
                self.check_cancel(is_cancelled)
                pct = 20 + int((idx / max(1, n_frames)) * 70)
                self.report_progress(progress_cb, pct, f"Running OCR on image page {idx}/{n_frames}")
                try:
                    extracted_text = ocr_service.extract_text_from_pil(frame.copy(), lang=ocr_lang)
                    ocr_used = True
                except OCRError as exc:
                    extracted_text = ""
                    metadata["ocr_warning"] = str(exc)

                pages.append(
                    ParsedPage(
                        page_number=idx,
                        title=f"Image {idx}" if n_frames > 1 else "Image",
                        text=extracted_text,
                        ocr_applied=ocr_used,
                        has_image_preview=True,
                    )
                )

        return ParsedDocument(pages=pages, metadata=metadata, ocr_used=ocr_used)
