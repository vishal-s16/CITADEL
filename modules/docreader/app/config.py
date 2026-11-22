"""DOCREADER configuration settings."""
from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "DOCREADER"
    app_version: str = "1.0.0"
    # Storage & Security
    base_dir: Path = Path(os.getenv("DOCREADER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
    upload_dir: Path = Path(os.getenv("DOCREADER_UPLOAD_DIR", Path(__file__).resolve().parent.parent / "data" / "uploads"))
    db_path: Path = Path(os.getenv("DOCREADER_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "docreader.db"))
    max_file_size_mb: int = int(os.getenv("DOCREADER_MAX_FILE_SIZE_MB", "100"))
    max_zip_uncompressed_mb: int = int(os.getenv("DOCREADER_MAX_ZIP_UNCOMPRESSED_MB", "300"))
    temp_file_ttl_minutes: int = int(os.getenv("DOCREADER_TEMP_FILE_TTL_MINUTES", "60"))
    cleanup_interval_seconds: int = int(os.getenv("DOCREADER_CLEANUP_INTERVAL_SECONDS", "300"))
    # OCR settings
    ocr_default_lang: str = os.getenv("DOCREADER_OCR_LANG", "eng")
    ocr_dpi: int = int(os.getenv("DOCREADER_OCR_DPI", "200"))
    ocr_min_text_chars_per_page: int = int(os.getenv("DOCREADER_OCR_MIN_CHARS", "25"))
    # AI settings (kept strictly server-side; never exposed to frontend)
    ai_provider: str = os.getenv("DOCREADER_AI_PROVIDER", "local")  # "local" | "openai" | "gemini"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("DOCREADER_OPENAI_MODEL", "gpt-4o-mini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("DOCREADER_GEMINI_MODEL", "gemini-2.0-flash")
    # CORS
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("DOCREADER_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000").split(",")
        if o.strip()
    ]
    # Chunking
    chunk_size_chars: int = int(os.getenv("DOCREADER_CHUNK_SIZE", "1200"))
    chunk_overlap_chars: int = int(os.getenv("DOCREADER_CHUNK_OVERLAP", "200"))

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
