"""Microsoft Word parser for DOCX (python-docx) and legacy DOC (LibreOffice conversion + olefile)."""
from __future__ import annotations

import html
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator, Optional

from docx import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

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


def _iter_block_items(doc: DocxDocument) -> Iterator[Paragraph | Table]:
    """Yield paragraphs and tables in exact document reading order."""
    parent_elm = doc.element.body
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def _convert_doc_to_docx(doc_path: Path, out_dir: Path) -> Path:
    """Convert legacy .doc to .docx using isolated headless LibreOffice."""
    with tempfile.TemporaryDirectory(prefix="lo_profile_") as lo_profile:
        env = {**os.environ, "HOME": "/tmp", "TMPDIR": "/tmp"}
        cmd = [
            "libreoffice",
            "--headless",
            f"-env:UserInstallation=file://{lo_profile}",
            "--convert-to",
            "docx",
            "--outdir",
            str(out_dir),
            str(doc_path),
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=45)
        converted = out_dir / f"{doc_path.stem}.docx"
        if proc.returncode != 0 or not converted.exists() or converted.stat().st_size == 0:
            raise CorruptedFileError(
                f"Failed to convert legacy .doc file: {proc.stderr.strip() or 'conversion produced no output'}"
            )
        return converted


class WordParser(DocumentParser):
    supported_formats = ("docx", "doc")

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
        if format_id == "doc":
            self.report_progress(progress_cb, 20, "Converting legacy Word (.doc) document")
            with tempfile.TemporaryDirectory(prefix="docreader_doc_") as tmpdir:
                converted_path = _convert_doc_to_docx(file_path, Path(tmpdir))
                return self._parse_docx(converted_path, progress_cb=progress_cb, is_cancelled=is_cancelled, source_format="doc")
        return self._parse_docx(file_path, progress_cb=progress_cb, is_cancelled=is_cancelled, source_format="docx")

    def _parse_docx(
        self,
        docx_path: Path,
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
        source_format: str,
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 35, "Reading Word document structure")
        try:
            doc = DocxDocument(str(docx_path))
        except Exception as exc:
            raise CorruptedFileError(f"Unable to parse Word document: {exc}") from exc

        props = doc.core_properties
        metadata: dict[str, Any] = {
            "source_format": source_format,
            "title": props.title or None,
            "author": props.author or None,
            "subject": props.subject or None,
            "created": props.created.isoformat() if props.created else None,
            "modified": props.modified.isoformat() if props.modified else None,
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}

        outline: list[ParsedOutlineItem] = []
        tables: list[ParsedTable] = []
        text_parts: list[str] = []
        html_parts: list[str] = []

        # Group into pages on explicit page breaks or every ~45 blocks for comfortable navigation
        pages: list[ParsedPage] = []
        current_page = 1
        table_idx = 0

        def _flush_page(page_num: int) -> None:
            nonlocal text_parts, html_parts
            if text_parts or html_parts:
                pages.append(
                    ParsedPage(
                        page_number=page_num,
                        title=f"Section {page_num}" if page_num > 1 else "Page 1",
                        text="\n\n".join(text_parts),
                        html=sanitize_html("\n".join(html_parts)),
                    )
                )
                text_parts = []
                html_parts = []

        for block in _iter_block_items(doc):
            self.check_cancel(is_cancelled)
            if isinstance(block, Paragraph):
                # Check for hard page break inside paragraph runs
                has_break = "w:br" in block._p.xml and 'w:type="page"' in block._p.xml
                raw_text = block.text.strip()
                style_name = (block.style.name if block.style else "") or ""

                if raw_text:
                    escaped = html.escape(raw_text)
                    if style_name.startswith("Heading"):
                        level_str = style_name.replace("Heading", "").strip()
                        level = int(level_str) if level_str.isdigit() else 1
                        level = max(1, min(6, level))
                        outline.append(ParsedOutlineItem(title=raw_text, level=level, page_number=current_page))
                        text_parts.append(f"{'#' * level} {raw_text}")
                        html_parts.append(f"<h{level}>{escaped}</h{level}>")
                    elif "List" in style_name:
                        text_parts.append(f"• {raw_text}")
                        html_parts.append(f"<ul><li>{escaped}</li></ul>")
                    else:
                        text_parts.append(raw_text)
                        html_parts.append(f"<p>{escaped}</p>")

                if has_break and text_parts:
                    _flush_page(current_page)
                    current_page += 1
            elif isinstance(block, Table):
                extracted_rows: list[list[str]] = []
                for row in block.rows:
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    if any(cells):
                        extracted_rows.append(cells)
                if extracted_rows:
                    headers = extracted_rows[0]
                    body_rows = extracted_rows[1:] if len(extracted_rows) > 1 else []
                    tables.append(
                        ParsedTable(
                            table_index=table_idx,
                            page_number=current_page,
                            title=f"Table {table_idx + 1}",
                            headers=headers,
                            rows=body_rows,
                        )
                    )
                    table_idx += 1

                    # Text representation preserving reading order
                    md_lines = [" | ".join(headers)]
                    for r in body_rows:
                        md_lines.append(" | ".join(r))
                    text_parts.append("\n".join(md_lines))

                    # HTML table representation
                    th_html = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
                    tr_html = "".join(
                        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>"
                        for r in body_rows
                    )
                    html_parts.append(f"<table><thead><tr>{th_html}</tr></thead><tbody>{tr_html}</tbody></table>")

        _flush_page(current_page)
        if not pages:
            pages.append(ParsedPage(page_number=1, title="Page 1", text="", html="<p><em>(Empty document)</em></p>"))

        self.report_progress(progress_cb, 90, "Finalizing Word document extraction")
        return ParsedDocument(pages=pages, tables=tables, outline=outline, metadata=metadata)
