"""Spreadsheet parser for XLSX (openpyxl), XLS (xlrd), and CSV."""
from __future__ import annotations

import csv
import html
from pathlib import Path
from typing import Any, Optional

import openpyxl
import xlrd

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

MAX_HTML_PREVIEW_ROWS = 250


def _build_sheet_html(title: str, headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    preview_rows = rows[:MAX_HTML_PREVIEW_ROWS]
    tr = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>"
        for r in preview_rows
    )
    note = ""
    if len(rows) > MAX_HTML_PREVIEW_ROWS:
        note = f"<p><small>Showing first {MAX_HTML_PREVIEW_ROWS} of {len(rows)} rows.</small></p>"
    return sanitize_html(
        f"<h3>{html.escape(title)}</h3>{note}<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"
    )


class SpreadsheetParser(DocumentParser):
    supported_formats = ("xlsx", "xls", "csv")

    def parse(
        self,
        file_path: Path,
        format_id: str,
        *,
        ocr_lang: str = "eng",
        progress_cb: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ParsedDocument:
        if format_id == "xlsx":
            return self._parse_xlsx(file_path, progress_cb=progress_cb, is_cancelled=is_cancelled)
        if format_id == "xls":
            return self._parse_xls(file_path, progress_cb=progress_cb, is_cancelled=is_cancelled)
        return self._parse_csv(file_path, progress_cb=progress_cb, is_cancelled=is_cancelled)

    def _parse_xlsx(
        self,
        file_path: Path,
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 20, "Opening Excel (.xlsx) workbook")
        try:
            wb = openpyxl.load_workbook(str(file_path), data_only=True, read_only=True)
        except Exception as exc:
            raise CorruptedFileError(f"Unable to open XLSX workbook: {exc}") from exc

        pages: list[ParsedPage] = []
        tables: list[ParsedTable] = []
        outline: list[ParsedOutlineItem] = []
        sheet_names = wb.sheetnames
        total = max(1, len(sheet_names))

        try:
            for idx, name in enumerate(sheet_names, start=1):
                self.check_cancel(is_cancelled)
                pct = 25 + int((idx / total) * 65)
                self.report_progress(progress_cb, pct, f"Reading worksheet '{name}' ({idx}/{total})")

                ws = wb[name]
                raw_rows: list[list[str]] = []
                for row in ws.iter_rows(values_only=True):
                    cells = ["" if v is None else str(v).strip() for v in row]
                    if any(cells):
                        raw_rows.append(cells)

                outline.append(ParsedOutlineItem(title=name, level=1, page_number=idx))
                if raw_rows:
                    max_cols = max(len(r) for r in raw_rows)
                    normalized = [r + [""] * (max_cols - len(r)) for r in raw_rows]
                    headers = normalized[0]
                    body = normalized[1:]
                    tables.append(
                        ParsedTable(table_index=idx - 1, page_number=idx, title=name, headers=headers, rows=body)
                    )
                    text = "\n".join(" | ".join(r) for r in normalized)
                    sheet_html = _build_sheet_html(name, headers, body)
                else:
                    text = f"(Empty worksheet: {name})"
                    sheet_html = f"<h3>{html.escape(name)}</h3><p><em>(Empty worksheet)</em></p>"

                pages.append(ParsedPage(page_number=idx, title=name, text=text, html=sheet_html))
        finally:
            wb.close()

        metadata: dict[str, Any] = {"sheet_count": len(sheet_names), "sheets": sheet_names}
        return ParsedDocument(pages=pages, tables=tables, outline=outline, metadata=metadata)

    def _parse_xls(
        self,
        file_path: Path,
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 20, "Opening legacy Excel (.xls) workbook")
        try:
            wb = xlrd.open_workbook(str(file_path))
        except Exception as exc:
            raise CorruptedFileError(f"Unable to open XLS workbook: {exc}") from exc

        pages: list[ParsedPage] = []
        tables: list[ParsedTable] = []
        outline: list[ParsedOutlineItem] = []
        total = max(1, wb.nsheets)

        for idx in range(wb.nsheets):
            self.check_cancel(is_cancelled)
            sheet = wb.sheet_by_index(idx)
            page_num = idx + 1
            self.report_progress(progress_cb, 25 + int((page_num / total) * 65), f"Reading sheet '{sheet.name}'")
            outline.append(ParsedOutlineItem(title=sheet.name, level=1, page_number=page_num))

            raw_rows: list[list[str]] = []
            for r in range(sheet.nrows):
                cells = [str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)]
                if any(cells):
                    raw_rows.append(cells)

            if raw_rows:
                headers = raw_rows[0]
                body = raw_rows[1:]
                tables.append(
                    ParsedTable(table_index=idx, page_number=page_num, title=sheet.name, headers=headers, rows=body)
                )
                text = "\n".join(" | ".join(r) for r in raw_rows)
                sheet_html = _build_sheet_html(sheet.name, headers, body)
            else:
                text = f"(Empty worksheet: {sheet.name})"
                sheet_html = f"<h3>{html.escape(sheet.name)}</h3><p><em>(Empty worksheet)</em></p>"

            pages.append(ParsedPage(page_number=page_num, title=sheet.name, text=text, html=sheet_html))

        metadata = {"sheet_count": wb.nsheets, "sheets": wb.sheet_names()}
        return ParsedDocument(pages=pages, tables=tables, outline=outline, metadata=metadata)

    def _parse_csv(
        self,
        file_path: Path,
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 30, "Parsing CSV data")
        raw_bytes = file_path.read_bytes()
        try:
            content = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1", errors="replace")

        lines = content.splitlines()
        if not lines:
            return ParsedDocument(
                pages=[ParsedPage(page_number=1, title="CSV Data", text="", html="<p><em>(Empty CSV)</em></p>")]
            )

        sample = "\n".join(lines[:20])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(lines, dialect=dialect)
        rows: list[list[str]] = []
        for row in reader:
            self.check_cancel(is_cancelled)
            cleaned = [c.strip() for c in row]
            if any(cleaned):
                rows.append(cleaned)

        if not rows:
            return ParsedDocument(
                pages=[ParsedPage(page_number=1, title="CSV Data", text="", html="<p><em>(Empty CSV)</em></p>")]
            )

        max_cols = max(len(r) for r in rows)
        normalized = [r + [""] * (max_cols - len(r)) for r in rows]
        headers = normalized[0]
        body = normalized[1:]
        table = ParsedTable(table_index=0, page_number=1, title="CSV Table", headers=headers, rows=body)
        text = "\n".join(" | ".join(r) for r in normalized)
        sheet_html = _build_sheet_html("CSV Table", headers, body)

        return ParsedDocument(
            pages=[ParsedPage(page_number=1, title="CSV Table", text=text, html=sheet_html)],
            tables=[table],
            outline=[ParsedOutlineItem(title="CSV Table", level=1, page_number=1)],
            metadata={"row_count": len(body), "column_count": max_cols, "delimiter": dialect.delimiter},
        )
