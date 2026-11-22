"""SQLite database layer for DOCREADER."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import settings


_LOCK = threading.RLock()


class Database:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or settings.db_path)
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema()
        except Exception:
            pass

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with _LOCK:
            try:
                conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            except Exception:
                conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
            except Exception:
                pass
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    stored_path TEXT,
                    detected_format TEXT NOT NULL,
                    category TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL DEFAULT 0,
                    page_count INTEGER NOT NULL DEFAULT 0,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    char_count INTEGER NOT NULL DEFAULT 0,
                    table_count INTEGER NOT NULL DEFAULT 0,
                    ocr_used INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT '',
                    error_message TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    outline_json TEXT NOT NULL DEFAULT '[]',
                    full_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                );

                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    title TEXT,
                    text TEXT NOT NULL DEFAULT '',
                    html TEXT,
                    ocr_applied INTEGER NOT NULL DEFAULT 0,
                    has_image_preview INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tables_extracted (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    table_index INTEGER NOT NULL,
                    page_number INTEGER NOT NULL DEFAULT 1,
                    title TEXT,
                    headers_json TEXT NOT NULL DEFAULT '[]',
                    rows_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER NOT NULL DEFAULT 1,
                    text TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_pages_doc ON pages(document_id, page_number);
                CREATE INDEX IF NOT EXISTS idx_tables_doc ON tables_extracted(document_id, table_index);
                CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id, chunk_index);
                """
            )

    def create_document(self, doc: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, filename, stored_path, detected_format, category, mime_type,
                    file_size, status, progress, stage, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc["id"],
                    doc["filename"],
                    doc.get("stored_path"),
                    doc.get("detected_format", "unknown"),
                    doc.get("category", "Other"),
                    doc.get("mime_type", "application/octet-stream"),
                    doc.get("file_size", 0),
                    doc.get("status", "queued"),
                    doc.get("progress", 0),
                    doc.get("stage", "Queued"),
                    doc.get("created_at", now),
                    doc.get("expires_at"),
                ),
            )

    def update_status(
        self,
        doc_id: str,
        *,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        stage: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if progress is not None:
            fields.append("progress = ?")
            values.append(progress)
        if stage is not None:
            fields.append("stage = ?")
            values.append(stage)
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)
        if not fields:
            return
        values.append(doc_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE documents SET {', '.join(fields)} WHERE id = ?", values)

    def save_parsed_content(
        self,
        doc_id: str,
        *,
        detected_format: str,
        category: str,
        mime_type: str,
        pages: list[dict[str, Any]],
        tables: list[dict[str, Any]],
        outline: list[dict[str, Any]],
        metadata: dict[str, Any],
        full_text: str,
        chunks: list[dict[str, Any]],
        ocr_used: bool,
    ) -> None:
        word_count = len(full_text.split()) if full_text.strip() else 0
        char_count = len(full_text)
        with self.connect() as conn:
            conn.execute("DELETE FROM pages WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM tables_extracted WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))

            conn.execute(
                """
                UPDATE documents
                SET detected_format = ?, category = ?, mime_type = ?,
                    page_count = ?, word_count = ?, char_count = ?, table_count = ?,
                    ocr_used = ?, status = 'completed', progress = 100, stage = 'Completed',
                    error_message = NULL, metadata_json = ?, outline_json = ?, full_text = ?
                WHERE id = ?
                """,
                (
                    detected_format,
                    category,
                    mime_type,
                    len(pages),
                    word_count,
                    char_count,
                    len(tables),
                    1 if ocr_used else 0,
                    json.dumps(metadata, default=str),
                    json.dumps(outline, default=str),
                    full_text,
                    doc_id,
                ),
            )

            for p in pages:
                conn.execute(
                    """
                    INSERT INTO pages (document_id, page_number, title, text, html, ocr_applied, has_image_preview)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        p["page_number"],
                        p.get("title"),
                        p.get("text", ""),
                        p.get("html"),
                        1 if p.get("ocr_applied") else 0,
                        1 if p.get("has_image_preview") else 0,
                    ),
                )

            for t in tables:
                conn.execute(
                    """
                    INSERT INTO tables_extracted (document_id, table_index, page_number, title, headers_json, rows_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        t["table_index"],
                        t.get("page_number", 1),
                        t.get("title"),
                        json.dumps(t.get("headers", []), default=str),
                        json.dumps(t.get("rows", []), default=str),
                    ),
                )

            for c in chunks:
                conn.execute(
                    """
                    INSERT INTO chunks (document_id, chunk_index, page_number, text)
                    VALUES (?, ?, ?, ?)
                    """,
                    (doc_id, c["chunk_index"], c.get("page_number", 1), c["text"]),
                )

    def get_document(self, doc_id: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            doc = dict(row)
            doc["ocr_used"] = bool(doc["ocr_used"])
            doc["metadata"] = json.loads(doc.pop("metadata_json") or "{}")
            doc["outline"] = json.loads(doc.pop("outline_json") or "[]")

            page_rows = conn.execute(
                "SELECT * FROM pages WHERE document_id = ? ORDER BY page_number ASC", (doc_id,)
            ).fetchall()
            table_rows = conn.execute(
                "SELECT * FROM tables_extracted WHERE document_id = ? ORDER BY table_index ASC", (doc_id,)
            ).fetchall()

            tables = [
                {
                    "table_index": r["table_index"],
                    "page_number": r["page_number"],
                    "title": r["title"],
                    "headers": json.loads(r["headers_json"] or "[]"),
                    "rows": json.loads(r["rows_json"] or "[]"),
                }
                for r in table_rows
            ]
            tables_by_page: dict[int, list[dict[str, Any]]] = {}
            for t in tables:
                tables_by_page.setdefault(t["page_number"], []).append(t)

            doc["pages"] = [
                {
                    "page_number": r["page_number"],
                    "title": r["title"],
                    "text": r["text"],
                    "html": r["html"],
                    "ocr_applied": bool(r["ocr_applied"]),
                    "has_image_preview": bool(r["has_image_preview"]),
                    "tables": tables_by_page.get(r["page_number"], []),
                }
                for r in page_rows
            ]
            doc["tables"] = tables
            return doc

    def get_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT chunk_index, page_number, text FROM chunks WHERE document_id = ? ORDER BY chunk_index ASC",
                (doc_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_documents(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, filename, detected_format, category, mime_type, file_size,
                       page_count, word_count, char_count, table_count, ocr_used,
                       status, progress, stage, error_message, created_at, expires_at
                FROM documents
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["ocr_used"] = bool(d["ocr_used"])
                result.append(d)
            return result

    def delete_document(self, doc_id: str) -> Optional[str]:
        with self.connect() as conn:
            row = conn.execute("SELECT stored_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            stored_path = row["stored_path"]
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return stored_path

    def clear_all(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT stored_path FROM documents").fetchall()
            paths = [r["stored_path"] for r in rows if r["stored_path"]]
            conn.execute("DELETE FROM documents")
            return paths

    def list_expired_temp_files(self, now_iso: str) -> list[tuple[str, str]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, stored_path FROM documents WHERE stored_path IS NOT NULL AND expires_at IS NOT NULL AND expires_at < ?",
                (now_iso,),
            ).fetchall()
            return [(r["id"], r["stored_path"]) for r in rows]

    def clear_stored_path(self, doc_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE documents SET stored_path = NULL WHERE id = ?", (doc_id,))

    def get_stats(self) -> dict[str, int]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_documents,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_documents,
                    COALESCE(SUM(page_count), 0) AS total_pages,
                    COALESCE(SUM(word_count), 0) AS total_words,
                    COALESCE(SUM(table_count), 0) AS total_tables,
                    SUM(CASE WHEN ocr_used = 1 THEN 1 ELSE 0 END) AS ocr_documents,
                    COALESCE(SUM(file_size), 0) AS storage_bytes
                FROM documents
                """
            ).fetchone()
            return {k: int(row[k] or 0) for k in row.keys()}


db = Database()
