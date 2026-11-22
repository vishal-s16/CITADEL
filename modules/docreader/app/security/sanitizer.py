"""HTML sanitization to prevent XSS and strip executable scripts/event handlers."""
from __future__ import annotations

from bs4 import BeautifulSoup, Comment

try:
    import bleach as _bleach
except ImportError:
    _bleach = None

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "code", "col", "colgroup",
    "dd", "del", "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "i", "li", "mark", "ol", "p", "pre", "q",
    "s", "section", "small", "span", "strong", "sub", "sup", "table", "tbody",
    "td", "tfoot", "th", "thead", "tr", "u", "ul",
}

ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    "a": ["href", "title", "rel"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "col": ["span"],
    "colgroup": ["span"],
    "*": ["class"],
}

ALLOWED_PROTOCOLS = ("http://", "https://", "mailto:", "#")
DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript", "svg", "math"}


def sanitize_html(raw_html: str) -> str:
    """Sanitize untrusted HTML while preserving safe structural markup."""
    if not raw_html:
        return ""
    if _bleach is not None:
        return _bleach.clean(
            raw_html,
            tags=list(ALLOWED_TAGS),
            attributes=ALLOWED_ATTRIBUTES,
            protocols=["http", "https", "mailto"],
            strip=True,
        )

    soup = BeautifulSoup(raw_html, "html.parser")
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for bad in soup.find_all(DROP_WITH_CONTENT):
        bad.decompose()

    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        allowed_for_tag = set(ALLOWED_ATTRIBUTES.get(tag.name, [])) | set(ALLOWED_ATTRIBUTES["*"])
        clean_attrs: dict[str, object] = {}
        for attr, val in list(tag.attrs.items()):
            attr_lower = attr.lower()
            if attr_lower.startswith("on") or attr_lower not in allowed_for_tag:
                continue
            if attr_lower == "href":
                href_str = str(val).strip()
                if not href_str.lower().startswith(ALLOWED_PROTOCOLS):
                    continue
                clean_attrs["href"] = href_str
                clean_attrs["rel"] = "noopener noreferrer"
            else:
                clean_attrs[attr_lower] = val
        tag.attrs = clean_attrs

    return str(soup)
