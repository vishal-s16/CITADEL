"""FastAPI router for /api/compression/* endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, File, Query, UploadFile

from ..controllers.compression_controller import (
    handle_cleanup,
    handle_compress,
    handle_download,
    handle_health,
    handle_status,
    handle_upload,
)

router = APIRouter(tags=["compression"])


@router.get("/health")
def health():
    return handle_health()


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    return await handle_upload(file)


@router.post("/compress")
def compress(
    payload: dict[str, Any] = Body(...),
    async_mode: bool = Query(False, alias="async"),
):
    return handle_compress(payload, async_mode=async_mode)


@router.get("/status/{job_id}")
def status(job_id: str):
    return handle_status(job_id)


@router.get("/download/{job_id}")
def download(job_id: str):
    return handle_download(job_id)


@router.delete("/cleanup/{job_id}")
def cleanup(job_id: str):
    return handle_cleanup(job_id)
