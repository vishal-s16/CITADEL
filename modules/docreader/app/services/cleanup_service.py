"""Automatic TTL cleanup service for temporary uploaded files."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from ..database import db

logger = logging.getLogger(__name__)


def purge_expired_files() -> int:
    """Delete temporary uploaded files whose TTL has expired."""
    now_iso = datetime.now(timezone.utc).isoformat()
    expired = db.list_expired_temp_files(now_iso)
    removed = 0
    for doc_id, stored_path in expired:
        try:
            p = Path(stored_path)
            if p.exists() and p.is_file():
                p.unlink()
                removed += 1
        except Exception as exc:
            logger.warning("Failed to delete expired temp file %s: %s", stored_path, exc)
        finally:
            db.clear_stored_path(doc_id)
    return removed


async def cleanup_loop() -> None:
    while True:
        try:
            removed = purge_expired_files()
            if removed:
                logger.info("Cleaned up %d expired temporary files.", removed)
        except Exception as exc:
            logger.warning("Cleanup loop error: %s", exc)
        await asyncio.sleep(settings.cleanup_interval_seconds)
