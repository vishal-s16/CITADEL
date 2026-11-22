"""Pydantic schemas for DOCREADER API requests and responses."""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class OutlineItem(BaseModel):
    title: str
    level: int = 1
    page_number: int = 1


class TableData(BaseModel):
    table_index: int
    page_number: int = 1
    title: Optional[str] = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class PageContent(BaseModel):
    page_number: int
    title: Optional[str] = None
    text: str = ""
    html: Optional[str] = None
    ocr_applied: bool = False
    tables: list[TableData] = Field(default_factory=list)
    has_image_preview: bool = False


class DocumentSummary(BaseModel):
    id: str
    filename: str
    detected_format: str
    category: str
    mime_type: str
    file_size: int
    page_count: int
    word_count: int
    char_count: int
    table_count: int
    ocr_used: bool
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    progress: int = 0
    stage: str = ""
    error_message: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None


class DocumentDetail(DocumentSummary):
    metadata: dict[str, Any] = Field(default_factory=dict)
    outline: list[OutlineItem] = Field(default_factory=list)
    pages: list[PageContent] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    full_text: str = ""
    paragraphs: list[str] = Field(default_factory=list)


class SearchMatch(BaseModel):
    page_number: int
    match_index: int
    start: int
    end: int
    matched_text: str
    snippet: str


class SearchResponse(BaseModel):
    document_id: str
    query: str
    case_sensitive: bool
    total_matches: int
    matches: list[SearchMatch] = Field(default_factory=list)


class AIQueryRequest(BaseModel):
    action: Literal[
        "ask",
        "summarize",
        "key_points",
        "explain_paragraph",
        "extract_entities",
        "explain_tables",
    ] = "ask"
    question: Optional[str] = None
    paragraph_text: Optional[str] = None
    allow_external_ai: bool = False


class AICitation(BaseModel):
    page_number: int
    chunk_index: int
    excerpt: str
    score: float


class AIQueryResponse(BaseModel):
    document_id: str
    action: str
    answer: str
    found_in_document: bool
    provider_used: str
    citations: list[AICitation] = Field(default_factory=list)
    structured_data: Optional[dict[str, Any]] = None


class OCRRunRequest(BaseModel):
    language: str = "eng"
    force_all_pages: bool = False


class StatsResponse(BaseModel):
    total_documents: int
    completed_documents: int
    total_pages: int
    total_words: int
    total_tables: int
    ocr_documents: int
    storage_bytes: int
    supported_formats: list[dict[str, Any]]
