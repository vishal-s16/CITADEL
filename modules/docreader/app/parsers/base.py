"""Universal Document Parser interface and intermediate representation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

ProgressCallback = Callable[[int, str], None]
CancelCheck = Callable[[], bool]


class ProcessingCancelledError(Exception):
    """Raised when a user cancels an in-flight document processing job."""


@dataclass
class ParsedTable:
    table_index: int
    page_number: int = 1
    title: Optional[str] = None
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_index": self.table_index,
            "page_number": self.page_number,
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
        }


@dataclass
class ParsedOutlineItem:
    title: str
    level: int = 1
    page_number: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "level": self.level,
            "page_number": self.page_number,
        }


@dataclass
class ParsedPage:
    page_number: int
    title: Optional[str] = None
    text: str = ""
    html: Optional[str] = None
    ocr_applied: bool = False
    has_image_preview: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "title": self.title,
            "text": self.text,
            "html": self.html,
            "ocr_applied": self.ocr_applied,
            "has_image_preview": self.has_image_preview,
        }


@dataclass
class ParsedDocument:
    pages: list[ParsedPage] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    outline: list[ParsedOutlineItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    ocr_used: bool = False

    @property
    def full_text(self) -> str:
        parts = [p.text.strip() for p in self.pages if p.text and p.text.strip()]
        return "\n\n".join(parts)


class DocumentParser(ABC):
    """Universal interface implemented by every format-specific parser.

    Adding a new format only requires subclassing DocumentParser and registering
    it in ParserRegistry.
    """

    supported_formats: tuple[str, ...] = ()

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        format_id: str,
        *,
        ocr_lang: str = "eng",
        progress_cb: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ParsedDocument:
        """Extract pages, tables, outline, and metadata from file_path."""

    @staticmethod
    def check_cancel(is_cancelled: Optional[CancelCheck]) -> None:
        if is_cancelled and is_cancelled():
            raise ProcessingCancelledError("Document processing was cancelled by the user.")

    @staticmethod
    def report_progress(progress_cb: Optional[ProgressCallback], pct: int, stage: str) -> None:
        if progress_cb:
            progress_cb(pct, stage)
