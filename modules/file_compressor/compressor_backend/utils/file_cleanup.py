"""Secure temporary storage and automatic TTL file cleanup utilities."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

BASE_TEMP_DIR = Path(
    os.environ.get("UFC_TEMP_DIR") or os.path.join(tempfile.gettempdir(), "universal-file-compressor")
).resolve()


def ensure_temp_root() -> Path:
    BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(BASE_TEMP_DIR, 0o700)
    except OSError:
        pass
    return BASE_TEMP_DIR


def create_job_directory(job_id: str | None = None) -> tuple[str, Path]:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id or str(uuid.uuid4()))
    job_dir = ensure_temp_root() / f"job_{safe_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(job_dir, 0o700)
    except OSError:
        pass
    return safe_id, job_dir


def is_inside_temp_root(target: Path) -> bool:
    try:
        target.resolve().relative_to(BASE_TEMP_DIR.resolve())
        return True
    except ValueError:
        return False


def safe_delete_file(file_path: str | Path | None) -> bool:
    if not file_path:
        return False
    p = Path(file_path)
    if is_inside_temp_root(p) and p.is_file():
        try:
            p.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    return False


def cleanup_job_directory(job_dir_or_id: str | Path | None) -> bool:
    if not job_dir_or_id:
        return False
    target = Path(job_dir_or_id)
    if not target.is_absolute():
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job_dir_or_id))
        target = ensure_temp_root() / f"job_{safe_id}"
    if is_inside_temp_root(target) and target.exists():
        try:
            shutil.rmtree(target, ignore_errors=True)
            return True
        except OSError:
            return False
    return False


def sweep_expired_files(max_age_seconds: int = 1800) -> int:
    root = ensure_temp_root()
    now = time.time()
    removed = 0
    for entry in root.iterdir():
        try:
            if now - entry.stat().st_mtime > max_age_seconds:
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    return removed


class AutoCleanupWorker:
    """Background daemon thread that periodically sweeps expired temporary job folders."""

    def __init__(self, max_age_seconds: int = 1800, interval_seconds: int = 300):
        self.max_age_seconds = max_age_seconds
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        ensure_temp_root()
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            sweep_expired_files(self.max_age_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        sweep_expired_files(0)
