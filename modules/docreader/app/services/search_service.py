"""Document search service with case-sensitive/insensitive phrase matching and snippets."""
from __future__ import annotations

import re
from typing import Any

from ..models import SearchMatch, SearchResponse


def search_document(
    doc: dict[str, Any],
    query: str,
    *,
    case_sensitive: bool = False,
    max_matches: int = 500,
) -> SearchResponse:
    cleaned_query = query.strip()
    if not cleaned_query:
        return SearchResponse(
            document_id=doc["id"],
            query=query,
            case_sensitive=case_sensitive,
            total_matches=0,
            matches=[],
        )

    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(cleaned_query), flags)

    matches: list[SearchMatch] = []
    match_counter = 0

    for page in doc.get("pages", []):
        page_num = int(page["page_number"])
        text = page.get("text") or ""
        for m in pattern.finditer(text):
            if len(matches) >= max_matches:
                break
            start, end = m.start(), m.end()
            ctx_start = max(0, start - 70)
            ctx_end = min(len(text), end + 90)
            snippet = text[ctx_start:ctx_end].replace("\n", " ").strip()
            if ctx_start > 0:
                snippet = "…" + snippet
            if ctx_end < len(text):
                snippet = snippet + "…"

            matches.append(
                SearchMatch(
                    page_number=page_num,
                    match_index=match_counter,
                    start=start,
                    end=end,
                    matched_text=m.group(0),
                    snippet=snippet,
                )
            )
            match_counter += 1
        if len(matches) >= max_matches:
            break

    return SearchResponse(
        document_id=doc["id"],
        query=cleaned_query,
        case_sensitive=case_sensitive,
        total_matches=len(matches),
        matches=matches,
    )
