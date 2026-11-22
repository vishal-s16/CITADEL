"""Microsoft PowerPoint parser for PPTX (python-pptx) and legacy PPT (LibreOffice conversion)."""
from __future__ import annotations

import html
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from pptx import Presentation

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


def _convert_ppt_to_pptx(ppt_path: Path, out_dir: Path) -> Path:
    with tempfile.TemporaryDirectory(prefix="lo_profile_") as lo_profile:
        env = {**os.environ, "HOME": "/tmp", "TMPDIR": "/tmp"}
        cmd = [
            "libreoffice",
            "--headless",
            f"-env:UserInstallation=file://{lo_profile}",
            "--convert-to",
            "pptx",
            "--outdir",
            str(out_dir),
            str(ppt_path),
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=45)
        converted = out_dir / f"{ppt_path.stem}.pptx"
        if proc.returncode != 0 or not converted.exists() or converted.stat().st_size == 0:
            raise CorruptedFileError(
                f"Failed to convert legacy .ppt file: {proc.stderr.strip() or 'conversion produced no output'}"
            )
        return converted


class PowerPointParser(DocumentParser):
    supported_formats = ("pptx", "ppt")

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
        if format_id == "ppt":
            self.report_progress(progress_cb, 20, "Converting legacy PowerPoint (.ppt) deck")
            with tempfile.TemporaryDirectory(prefix="docreader_ppt_") as tmpdir:
                converted = _convert_ppt_to_pptx(file_path, Path(tmpdir))
                return self._parse_pptx(converted, progress_cb=progress_cb, is_cancelled=is_cancelled, source_format="ppt")
        return self._parse_pptx(file_path, progress_cb=progress_cb, is_cancelled=is_cancelled, source_format="pptx")

    def _parse_pptx(
        self,
        pptx_path: Path,
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
        source_format: str,
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 30, "Opening PowerPoint presentation")
        try:
            prs = Presentation(str(pptx_path))
        except Exception as exc:
            raise CorruptedFileError(f"Unable to open PowerPoint presentation: {exc}") from exc

        props = prs.core_properties
        metadata: dict[str, Any] = {
            "source_format": source_format,
            "slide_count": len(prs.slides),
            "title": props.title or None,
            "author": props.author or None,
            "subject": props.subject or None,
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}

        pages: list[ParsedPage] = []
        tables: list[ParsedTable] = []
        outline: list[ParsedOutlineItem] = []
        table_idx = 0
        total_slides = max(1, len(prs.slides))

        for slide_num, slide in enumerate(prs.slides, start=1):
            self.check_cancel(is_cancelled)
            pct = 35 + int((slide_num / total_slides) * 55)
            self.report_progress(progress_cb, pct, f"Extracting slide {slide_num} of {total_slides}")

            slide_title = ""
            if slide.shapes.title and slide.shapes.title.text:
                slide_title = slide.shapes.title.text.strip()
            display_title = slide_title or f"Slide {slide_num}"
            outline.append(ParsedOutlineItem(title=display_title, level=1, page_number=slide_num))

            text_lines: list[str] = []
            html_parts: list[str] = [f"<h2>{html.escape(display_title)}</h2>"]

            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        p_text = para.text.strip()
                        if not p_text:
                            continue
                        if p_text == slide_title and not text_lines:
                            text_lines.append(p_text)
                            continue
                        indent = "  " * (para.level or 0)
                        text_lines.append(f"{indent}• {p_text}" if (para.level or 0) > 0 else p_text)
                        html_parts.append(f"<p>{html.escape(p_text)}</p>")

                if shape.has_table:
                    tbl = shape.table
                    extracted_rows: list[list[str]] = []
                    for row in tbl.rows:
                        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                        if any(cells):
                            extracted_rows.append(cells)
                    if extracted_rows:
                        headers = extracted_rows[0]
                        body = extracted_rows[1:] if len(extracted_rows) > 1 else []
                        tables.append(
                            ParsedTable(
                                table_index=table_idx,
                                page_number=slide_num,
                                title=f"Slide {slide_num} Table {table_idx + 1}",
                                headers=headers,
                                rows=body,
                            )
                        )
                        table_idx += 1
                        text_lines.append(" | ".join(headers))
                        for r in body:
                            text_lines.append(" | ".join(r))
                        th_html = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
                        tr_html = "".join(
                            "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>"
                            for r in body
                        )
                        html_parts.append(f"<table><thead><tr>{th_html}</tr></thead><tbody>{tr_html}</tbody></table>")

            # Speaker notes
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    text_lines.append(f"\n[Speaker Notes]\n{notes}")
                    html_parts.append(f"<blockquote><strong>Speaker Notes:</strong> {html.escape(notes)}</blockquote>")

            pages.append(
                ParsedPage(
                    page_number=slide_num,
                    title=display_title,
                    text="\n".join(text_lines),
                    html=sanitize_html("\n".join(html_parts)),
                )
            )

        if not pages:
            pages.append(ParsedPage(page_number=1, title="Slide 1", text="", html="<p><em>(Empty presentation)</em></p>"))

        return ParsedDocument(pages=pages, tables=tables, outline=outline, metadata=metadata)
