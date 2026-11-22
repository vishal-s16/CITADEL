"""OCR engine service powered by Tesseract OCR and Pillow."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps
import pytesseract

from ..config import settings

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Raised when OCR extraction fails."""


class OCRService:
    """Wrapper around Tesseract OCR with image preprocessing and language detection."""

    def get_available_languages(self) -> list[str]:
        try:
            langs = pytesseract.get_languages(config="")
            return sorted(lang for lang in langs if lang != "osd")
        except Exception as exc:
            logger.warning("Could not list Tesseract languages: %s", exc)
            return ["eng"]

    def _resolve_language(self, requested: Optional[str]) -> str:
        available = set(self.get_available_languages())
        lang = (requested or settings.ocr_default_lang or "eng").strip()
        if not available:
            return "eng"
        parts = [p.strip() for p in lang.split("+") if p.strip()]
        valid = [p for p in parts if p in available]
        return "+".join(valid) if valid else ("eng" if "eng" in available else next(iter(available)))

    @staticmethod
    def _preprocess_image(img: Image.Image) -> Image.Image:
        # Handle EXIF orientation & convert to RGB/grayscale for cleaner OCR
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        # Upscale very small images for better character recognition
        w, h = img.size
        if max(w, h) < 800:
            scale = 2
            img = img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(img)
        gray = ImageOps.autocontrast(gray)
        return gray

    def extract_text_from_pil(self, img: Image.Image, lang: Optional[str] = None) -> str:
        resolved_lang = self._resolve_language(lang)
        try:
            processed = self._preprocess_image(img)
            text = pytesseract.image_to_string(processed, lang=resolved_lang)
            return text.strip()
        except Exception as exc:
            raise OCRError(f"OCR failed ({resolved_lang}): {exc}") from exc

    def extract_text_from_path(self, image_path: Path, lang: Optional[str] = None) -> str:
        try:
            with Image.open(image_path) as img:
                return self.extract_text_from_pil(img, lang=lang)
        except OCRError:
            raise
        except Exception as exc:
            raise OCRError(f"Failed to open image for OCR: {exc}") from exc


ocr_service = OCRService()
