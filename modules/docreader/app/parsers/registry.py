"""Modular parser registry enabling plug-and-play support for new document formats."""
from __future__ import annotations

from typing import Optional

from ..security.file_validator import FORMAT_CATALOG, UnsupportedFormatError
from .base import DocumentParser
from .image_parser import ImageParser
from .opendocument_parser import OpenDocumentParser
from .pdf_parser import PDFParser
from .powerpoint_parser import PowerPointParser
from .spreadsheet_parser import SpreadsheetParser
from .text_parser import TextParser
from .web_data_parser import WebDataParser


class ParserRegistry:
    """Central registry mapping detected format IDs to DocumentParser implementations."""

    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for parser in (
            PDFParser(),
            WordParser(),
            PowerPointParser(),
            SpreadsheetParser(),
            TextParser(),
            OpenDocumentParser(),
            WebDataParser(),
            ImageParser(),
        ):
            self.register(parser)

    def register(self, parser: DocumentParser) -> None:
        for fmt in parser.supported_formats:
            self._parsers[fmt.lower()] = parser

    def get(self, format_id: str) -> DocumentParser:
        parser: Optional[DocumentParser] = self._parsers.get(format_id.lower())
        if not parser:
            raise UnsupportedFormatError(f"No parser registered for format '{format_id}'.")
        return parser

    def list_supported_formats(self) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for fmt in sorted(self._parsers.keys()):
            category, mime_type = FORMAT_CATALOG.get(fmt, ("Other", "application/octet-stream"))
            items.append(
                {
                    "format": fmt.upper(),
                    "extension": f".{fmt}",
                    "category": category,
                    "mime_type": mime_type,
                    "parser": self._parsers[fmt].__class__.__name__,
                }
            )
        return items


from .word_parser import WordParser  # noqa: E402

parser_registry = ParserRegistry()
