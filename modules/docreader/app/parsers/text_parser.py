"""Text document parser for TXT, Markdown (MD), and Rich Text Format (RTF)."""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
import markdown as md_lib
from striprtf.striprtf import rtf_to_text

from ..security.file_validator import CorruptedFileError
from ..security.sanitizer import sanitize_html
from .base import (
    CancelCheck,
    DocumentParser,
    ParsedDocument,
    ParsedOutlineItem,
    ParsedPage,
    ParsedTable,
    ProgressCallback,
)

LINES_PER_TEXT_PAGE = 120


def _read_text_smart(file_path: Path) -> str:
    raw = file_path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class TextParser(DocumentParser):
    supported_formats = ("txt", "md", "rtf")

    def parse(
        self,
        file_path: Path,
        format_id: str,
        *,
        ocr_lang: str = "eng",
        progress_cb: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ParsedDocument:
        self.check_cancel(is_cancelled)
        if format_id == "md":
            return self._parse_markdown(file_path, progress_cb=progress_cb)
        if format_id == "rtf":
            return self._parse_rtf(file_path, progress_cb=progress_cb)
        return self._parse_txt(file_path, progress_cb=progress_cb)

    def _parse_txt(self, file_path: Path, *, progress_cb: Optional[ProgressCallback]) -> ParsedDocument:
        self.report_progress(progress_cb, 35, "Reading plain text document")
        content = _read_text_smart(file_path).replace("\r\n", "\n").replace("\r", "\n")
        lines = content.split("\n")

        pages: list[ParsedPage] = []
        for i in range(0, max(1, len(lines)), LINES_PER_TEXT_PAGE):
            chunk_lines = lines[i : i + LINES_PER_TEXT_PAGE]
            page_num = (i // LINES_PER_TEXT_PAGE) + 1
            page_text = "\n".join(chunk_lines)
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
            page_html = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
            pages.append(
                ParsedPage(
                    page_number=page_num,
                    title=f"Page {page_num}",
                    text=page_text,
                    html=sanitize_html(page_html or "<p></p>"),
                )
            )

        return ParsedDocument(
            pages=pages,
            metadata={"line_count": len(lines), "encoding": "utf-8"},
        )

    def _parse_markdown(self, file_path: Path, *, progress_cb: Optional[ProgressCallback]) -> ParsedDocument:
        self.report_progress(progress_cb, 35, "Rendering Markdown document")
        raw_md = _read_text_smart(file_path).replace("\r\n", "\n")
        rendered_html = md_lib.markdown(
            raw_md,
            extensions=["tables", "fenced_code", "toc", "nl2br"],
        )
        safe_html = sanitize_html(rendered_html)
        soup = BeautifulSoup(safe_html, "html.parser")

        outline: list[ParsedOutlineItem] = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(tag.name[1])
            title = tag.get_text(" ", strip=True)
            if title:
                outline.append(ParsedOutlineItem(title=title, level=level, page_number=1))

        tables: list[ParsedTable] = []
        for idx, tbl in enumerate(soup.find_all("table")):
            rows_data: list[list[str]] = []
            for tr in tbl.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                if any(cells):
                    rows_data.append(cells)
            if rows_data:
                tables.append(
                    ParsedTable(
                        table_index=idx,
                        page_number=1,
                        title=f"Markdown Table {idx + 1}",
                        headers=rows_data[0],
                        rows=rows_data[1:],
                    )
                )

        # Clean plain text preserving paragraph structure
        plain_text = soup.get_text("\n", strip=False)
        plain_text = re.sub(r"\n{3,}", "\n\n", plain_text).strip()

        return ParsedDocument(
            pages=[ParsedPage(page_number=1, title="Markdown Document", text=plain_text, html=safe_html)],
            tables=tables,
            outline=outline,
            metadata={"heading_count": len(outline), "table_count": len(tables)},
        )

    def _parse_rtf(self, file_path: Path, *, progress_cb: Optional[ProgressCallback]) -> ParsedDocument:
        self.report_progress(progress_cb, 35, "Extracting Rich Text Format (.rtf)")
        raw = _read_text_smart(file_path)
        try:
            extracted = rtf_to_text(raw).strip()
        except Exception as exc:
            raise CorruptedFileError(f"Failed to parse RTF document: {exc}") from exc

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", extracted) if p.strip()]
        if not paragraphs and extracted:
            paragraphs = [line.strip() for line in extracted.splitlines() if line.strip()]
        page_html = "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)

        return ParsedDocument(
            pages=[
                ParsedPage(
                    page_number=1,
                    title="RTF Document",
                    text="\n\n".join(paragraphs) if paragraphs else extracted,
                    html=sanitize_html(page_html or "<p></p>"),
                )
            ],
            metadata={"paragraph_count": len(paragraphs)},
        )
