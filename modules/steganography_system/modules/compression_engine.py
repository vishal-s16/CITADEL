"""Lossless payload compression and decompression using zlib."""

from __future__ import annotations

import zlib

from modules.exceptions import CompressionError


def compress_data(data: bytes, level: int = 6) -> bytes:
    """Compress raw bytes with zlib."""
    try:
        return zlib.compress(data, level=level)
    except (zlib.error, MemoryError) as exc:
        raise CompressionError("Failed to compress payload data.") from exc


def decompress_data(data: bytes) -> bytes:
    """Decompress zlib-compressed bytes."""
    try:
        return zlib.decompress(data)
    except zlib.error as exc:
        raise CompressionError(
            "Hidden payload appears corrupted and could not be decompressed."
        ) from exc
    except MemoryError as exc:
        raise CompressionError(
            "Insufficient memory to decompress the hidden payload."
        ) from exc
