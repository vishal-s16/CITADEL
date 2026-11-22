"""OpenDocument parser for ODT, ODS, and ODP using safe lxml XML extraction."""
from __future__ import annotations

import html
import zipfile
from pathlib import Path
from typing import Any, Optional

from lxml import etree

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

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
}

_SAFE_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)


def _node_text(el: etree._Element) -> str:
    return "".join(el.itertext()).strip()


def _extract_meta(zf: zipfile.ZipFile) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if "meta.xml" not in zf.namelist():
        return meta
    try:
        root = etree.fromstring(zf.read("meta.xml"), parser=_SAFE_XML_PARSER)
        for tag, key in (("dc:title", "title"), ("dc:creator", "author"), ("dc:subject", "subject")):
            node = root.find(f".//{tag}", namespaces=NS)
            if node is not None and node.text and node.text.strip():
                meta[key] = node.text.strip()
    except Exception:
        pass
    return meta


def _extract_odf_table(tbl_el: etree._Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in tbl_el.findall(".//table:table-row", namespaces=NS):
        row_cells: list[str] = []
        for cell in tr.findall("./table:table-cell", namespaces=NS):
            repeat = int(cell.get(f"{{{NS['table']}}}number-columns-repeated", "1"))
            val = " ".join(_node_text(p) for p in cell.findall(".//text:p", namespaces=NS)).strip()
            # Avoid expanding trailing empty columns in ODS sheets
            if not val and repeat > 20:
                continue
            row_cells.extend([val] * min(repeat, 50))
        while row_cells and not row_cells[-1]:
            row_cells.pop()
        if any(row_cells):
            rows.append(row_cells)
    return rows


class OpenDocumentParser(DocumentParser):
    supported_formats = ("odt", "ods", "odp")

    def parse(
        self,
        file_path: Path,
        format_id: str,
        *,
        ocr_lang: str = "eng",
        progress_cb: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 20, f"Opening OpenDocument (.{format_id})")
        try:
            with zipfile.ZipFile(file_path) as zf:
                if "content.xml" not in zf.namelist():
                    raise CorruptedFileError(f"OpenDocument .{format_id} is missing content.xml.")
                content_root = etree.fromstring(zf.read("content.xml"), parser=_SAFE_XML_PARSER)
                metadata = _extract_meta(zf)
        except CorruptedFileError:
            raise
        except Exception as exc:
            raise CorruptedFileError(f"Unable to parse OpenDocument .{format_id}: {exc}") from exc

        if format_id == "odt":
            return self._parse_odt(content_root, metadata, progress_cb=progress_cb, is_cancelled=is_cancelled)
        if format_id == "ods":
            return self._parse_ods(content_root, metadata, progress_cb=progress_cb, is_cancelled=is_cancelled)
        return self._parse_odp(content_root, metadata, progress_cb=progress_cb, is_cancelled=is_cancelled)

    def _parse_odt(
        self,
        root: etree._Element,
        metadata: dict[str, Any],
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 50, "Extracting ODT text and tables")
        body = root.find(".//office:text", namespaces=NS)
        if body is None:
            raise CorruptedFileError("ODT document has no office:text body.")

        text_parts: list[str] = []
        html_parts: list[str] = []
        outline: list[ParsedOutlineItem] = []
        tables: list[ParsedTable] = []
        table_idx = 0

        for child in body:
            self.check_cancel(is_cancelled)
            local = etree.QName(child).localname
            if local == "h":
                txt = _node_text(child)
                if txt:
                    level = int(child.get(f"{{{NS['text']}}}outline-level", "1"))
                    level = max(1, min(6, level))
                    outline.append(ParsedOutlineItem(title=txt, level=level, page_number=1))
                    text_parts.append(f"{'#' * level} {txt}")
                    html_parts.append(f"<h{level}>{html.escape(txt)}</h{level}>")
            elif local == "p":
                txt = _node_text(child)
                if txt:
                    text_parts.append(txt)
                    html_parts.append(f"<p>{html.escape(txt)}</p>")
            elif local == "list":
                items = [_node_text(li) for li in child.findall(".//text:list-item", namespaces=NS)]
                items = [i for i in items if i]
                if items:
                    for i in items:
                        text_parts.append(f"• {i}")
                    li_html = "".join(f"<li>{html.escape(i)}</li>" for i in items)
                    html_parts.append(f"<ul>{li_html}</ul>")
            elif local == "table":
                rows = _extract_odf_table(child)
                if rows:
                    max_c = max(len(r) for r in rows)
                    norm = [r + [""] * (max_c - len(r)) for r in rows]
                    headers, body_rows = norm[0], norm[1:]
                    tables.append(
                        ParsedTable(table_index=table_idx, page_number=1, title=f"Table {table_idx + 1}", headers=headers, rows=body_rows)
                    )
                    table_idx += 1
                    text_parts.append("\n".join(" | ".join(r) for r in norm))
                    th = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
                    tr = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in body_rows)
                    html_parts.append(f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>")

        page = ParsedPage(
            page_number=1,
            title="ODT Document",
            text="\n\n".join(text_parts),
            html=sanitize_html("\n".join(html_parts) or "<p></p>"),
        )
        return ParsedDocument(pages=[page], tables=tables, outline=outline, metadata=metadata)

    def _parse_ods(
        self,
        root: etree._Element,
        metadata: dict[str, Any],
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 50, "Extracting ODS spreadsheets")
        sheets = root.findall(".//office:spreadsheet/table:table", namespaces=NS)
        if not sheets:
            raise CorruptedFileError("ODS document contains no spreadsheets.")

        pages: list[ParsedPage] = []
        tables: list[ParsedTable] = []
        outline: list[ParsedOutlineItem] = []

        for idx, sheet in enumerate(sheets, start=1):
            self.check_cancel(is_cancelled)
            name = sheet.get(f"{{{NS['table']}}}name") or f"Sheet {idx}"
            outline.append(ParsedOutlineItem(title=name, level=1, page_number=idx))
            rows = _extract_odf_table(sheet)
            if rows:
                max_c = max(len(r) for r in rows)
                norm = [r + [""] * (max_c - len(r)) for r in rows]
                headers, body_rows = norm[0], norm[1:]
                tables.append(ParsedTable(table_index=idx - 1, page_number=idx, title=name, headers=headers, rows=body_rows))
                text = "\n".join(" | ".join(r) for r in norm)
                th = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
                tr = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in body_rows[:250])
                sheet_html = sanitize_html(f"<h3>{html.escape(name)}</h3><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>")
            else:
                text = f"(Empty sheet: {name})"
                sheet_html = sanitize_html(f"<h3>{html.escape(name)}</h3><p><em>(Empty sheet)</em></p>")
            pages.append(ParsedPage(page_number=idx, title=name, text=text, html=sheet_html))

        metadata["sheet_count"] = len(sheets)
        return ParsedDocument(pages=pages, tables=tables, outline=outline, metadata=metadata)

    def _parse_odp(
        self,
        root: etree._Element,
        metadata: dict[str, Any],
        *,
        progress_cb: Optional[ProgressCallback],
        is_cancelled: Optional[CancelCheck],
    ) -> ParsedDocument:
        self.report_progress(progress_cb, 50, "Extracting ODP presentation slides")
        slides = root.findall(".//office:presentation/draw:page", namespaces=NS)
        if not slides:
            raise CorruptedFileError("ODP presentation contains no slides.")

        pages: list[ParsedPage] = []
        tables: list[ParsedTable] = []
        outline: list[ParsedOutlineItem] = []
        table_idx = 0

        for idx, slide in enumerate(slides, start=1):
            self.check_cancel(is_cancelled)
            name = slide.get(f"{{{NS['draw']}}}name") or f"Slide {idx}"
            paragraphs = [_node_text(p) for p in slide.findall(".//text:p", namespaces=NS)]
            paragraphs = [p for p in paragraphs if p]
            title = paragraphs[0] if paragraphs else name
            outline.append(ParsedOutlineItem(title=title[:80], level=1, page_number=idx))

            html_parts = [f"<h2>{html.escape(title)}</h2>"] + [f"<p>{html.escape(p)}</p>" for p in paragraphs[1:]]

            for tbl_el in slide.findall(".//table:table", namespaces=NS):
                rows = _extract_odf_table(tbl_el)
                if rows:
                    max_c = max(len(r) for r in rows)
                    norm = [r + [""] * (max_c - len(r)) for r in rows]
                    tables.append(
                        ParsedTable(table_index=table_idx, page_number=idx, title=f"Slide {idx} Table", headers=norm[0], rows=norm[1:])
                    )
                    table_idx += 1

            pages.append(
                ParsedPage(
                    page_number=idx,
                    title=title[:80],
                    text="\n\n".join(paragraphs),
                    html=sanitize_html("\n".join(html_parts)),
                )
            )

        metadata["slide_count"] = len(slides)
        return ParsedDocument(pages=pages, tables=tables, outline=outline, metadata=metadata)
