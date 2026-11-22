"""Web and structured data parser for HTML, XML, and JSON."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup
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

_SAFE_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)


class WebDataParser(DocumentParser):
    supported_formats = ("html", "xml", "json")

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
        if format_id == "html":
            return self._parse_html(file_path, progress_cb=progress_cb)
        if format_id == "xml":
            return self._parse_xml(file_path, progress_cb=progress_cb)
        return self._parse_json(file_path, progress_cb=progress_cb)

    def _parse_html(self, file_path: Path, *, progress_cb: Optional[ProgressCallback]) -> ParsedDocument:
        self.report_progress(progress_cb, 35, "Parsing and sanitizing HTML")
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "html.parser")

        title = soup.title.get_text(" ", strip=True) if soup.title else None
        # Strip scripts, styles, iframes, objects before extracting text or HTML
        for bad in soup(["script", "style", "noscript", "iframe", "object", "embed"]):
            bad.decompose()

        body_html = str(soup.body) if soup.body else str(soup)
        safe_html = sanitize_html(body_html)

        outline: list[ParsedOutlineItem] = []
        for h_tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            h_txt = h_tag.get_text(" ", strip=True)
            if h_txt:
                outline.append(ParsedOutlineItem(title=h_txt, level=int(h_tag.name[1]), page_number=1))

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
                        title=f"HTML Table {idx + 1}",
                        headers=rows_data[0],
                        rows=rows_data[1:],
                    )
                )

        text = soup.get_text("\n", strip=False)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        metadata = {"title": title} if title else {}

        return ParsedDocument(
            pages=[ParsedPage(page_number=1, title=title or "HTML Document", text=text, html=safe_html)],
            tables=tables,
            outline=outline,
            metadata=metadata,
        )

    def _parse_xml(self, file_path: Path, *, progress_cb: Optional[ProgressCallback]) -> ParsedDocument:
        self.report_progress(progress_cb, 35, "Parsing XML structure")
        raw_bytes = file_path.read_bytes()
        try:
            root = etree.fromstring(raw_bytes, parser=_SAFE_XML_PARSER)
        except Exception as exc:
            raise CorruptedFileError(f"Invalid XML document: {exc}") from exc

        pretty_xml = etree.tostring(root, pretty_print=True, encoding="unicode")
        outline: list[ParsedOutlineItem] = []
        text_lines: list[str] = []

        def _walk(node: etree._Element, depth: int = 0) -> None:
            tag = etree.QName(node).localname
            if depth <= 1 and len(outline) < 100:
                outline.append(ParsedOutlineItem(title=tag, level=depth + 1, page_number=1))
            val = (node.text or "").strip()
            if val:
                text_lines.append(f"{'  ' * depth}{tag}: {val}")
            for child in node:
                if isinstance(child.tag, str):
                    _walk(child, depth + 1)

        _walk(root)
        plain_text = "\n".join(text_lines) or pretty_xml
        safe_html = sanitize_html(f"<pre><code>{html.escape(pretty_xml)}</code></pre>")

        return ParsedDocument(
            pages=[ParsedPage(page_number=1, title=f"XML ({etree.QName(root).localname})", text=plain_text, html=safe_html)],
            outline=outline,
            metadata={"root_tag": etree.QName(root).localname, "element_count": len(list(root.iter()))},
        )

    def _parse_json(self, file_path: Path, *, progress_cb: Optional[ProgressCallback]) -> ParsedDocument:
        self.report_progress(progress_cb, 35, "Parsing JSON payload")
        raw = file_path.read_text(encoding="utf-8-sig", errors="strict")
        try:
            data: Any = json.loads(raw)
        except Exception as exc:
            raise CorruptedFileError(f"Invalid JSON document: {exc}") from exc

        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        outline: list[ParsedOutlineItem] = []
        tables: list[ParsedTable] = []

        if isinstance(data, dict):
            for k in list(data.keys())[:100]:
                outline.append(ParsedOutlineItem(title=str(k), level=1, page_number=1))
            # Check if any top-level value is a list of homogeneous dicts -> extract as table
            for idx, (k, v) in enumerate(data.items()):
                if isinstance(v, list) and v and all(isinstance(item, dict) for item in v[:20]):
                    headers = list(dict.fromkeys(key for item in v[:50] if isinstance(item, dict) for key in item.keys()))
                    rows = [[str(item.get(h, "")) for h in headers] for item in v if isinstance(item, dict)]
                    tables.append(ParsedTable(table_index=len(tables), page_number=1, title=str(k), headers=headers, rows=rows))
        elif isinstance(data, list) and data and all(isinstance(item, dict) for item in data[:20]):
            headers = list(dict.fromkeys(key for item in data[:50] if isinstance(item, dict) for key in item.keys()))
            rows = [[str(item.get(h, "")) for h in headers] for item in data if isinstance(item, dict)]
            tables.append(ParsedTable(table_index=0, page_number=1, title="JSON Array", headers=headers, rows=rows))
            outline.append(ParsedOutlineItem(title=f"Array ({len(data)} items)", level=1, page_number=1))

        safe_html = sanitize_html(f"<pre><code>{html.escape(pretty)}</code></pre>")
        return ParsedDocument(
            pages=[ParsedPage(page_number=1, title="JSON Data", text=pretty, html=safe_html)],
            tables=tables,
            outline=outline,
            metadata={"json_type": type(data).__name__, "item_count": len(data) if isinstance(data, (dict, list)) else 1},
        )
