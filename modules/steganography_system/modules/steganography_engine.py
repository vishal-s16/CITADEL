"""RGB Least Significant Bit (LSB) steganography encoding engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

from modules import file_manager, image_handler, payload_manager
from modules.exceptions import CapacityExceededError
from modules.file_manager import PayloadFile
from modules.image_handler import ImageInfo, format_bytes, format_capacity_all_units

ALGORITHM_NAME = "RGB Least Significant Bit (LSB) + zlib"
ALGORITHM_NAME_ENCRYPTED = "RGB Least Significant Bit (LSB) + zlib + AES-256-GCM"

# Embed 1 MB (8M bits) per chunk to keep peak RAM low for large payloads
_EMBED_CHUNK_BYTES = 1024 * 1024

ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True)
class CapacityAnalysis:
    """Comparison of available image capacity vs. required payload storage."""

    available_bytes: int
    required_bytes: int
    remaining_bytes: int
    fits: bool
    raw_files_size_bytes: int
    file_count: int

    def to_dict(self) -> dict:
        return {
            "available_bytes": self.available_bytes,
            "available": format_capacity_all_units(self.available_bytes),
            "required_bytes": self.required_bytes,
            "required": format_capacity_all_units(self.required_bytes),
            "remaining_bytes": self.remaining_bytes,
            "remaining": format_capacity_all_units(max(0, self.remaining_bytes)),
            "overflow_bytes": max(0, self.required_bytes - self.available_bytes),
            "fits": self.fits,
            "raw_files_size_bytes": self.raw_files_size_bytes,
            "raw_files_size_formatted": format_bytes(self.raw_files_size_bytes),
            "file_count": self.file_count,
            "utilization_percent": round(
                min(100.0, (self.required_bytes / self.available_bytes) * 100.0), 2
            )
            if self.available_bytes > 0
            else 100.0,
        }


@dataclass(frozen=True)
class EncodeResult:
    """Complete result from an RGB LSB encoding operation."""

    encoded_png_bytes: bytes
    image_info: ImageInfo
    encoded_size_bytes: int
    embedded_payload_bytes: int
    raw_files_size_bytes: int
    file_count: int
    filenames: List[str]
    encrypted: bool
    algorithm: str
    steps_completed: List[str]


def embed_bytes_into_rgb_array(pixel_array: np.ndarray, payload_bytes: bytes) -> np.ndarray:
    """Embed payload_bytes into the LSB of every RGB channel in pixel_array using chunked writes."""
    flat_pixels = pixel_array.reshape(-1)
    max_bytes = flat_pixels.size // 8
    total_len = len(payload_bytes)

    if total_len > max_bytes:
        raise CapacityExceededError(
            f"Payload requires {format_bytes(total_len)} ({total_len:,} bytes), "
            f"which exceeds the image's capacity of {format_bytes(max_bytes)} ({max_bytes:,} bytes)."
        )

    encoded_flat = flat_pixels.copy()
    payload_uint8 = np.frombuffer(payload_bytes, dtype=np.uint8)

    offset = 0
    while offset < total_len:
        chunk_end = min(total_len, offset + _EMBED_CHUNK_BYTES)
        bits = np.unpackbits(payload_uint8[offset:chunk_end], bitorder="big")
        bit_start = offset * 8
        bit_end = chunk_end * 8
        encoded_flat[bit_start:bit_end] = (encoded_flat[bit_start:bit_end] & np.uint8(0xFE)) | bits
        offset = chunk_end

    return encoded_flat.reshape(pixel_array.shape)


def analyze_storage_capacity(
    image_bytes: bytes,
    image_filename: str,
    files: Sequence[Tuple[str, bytes]],
    category: Optional[str] = None,
    use_encryption: bool = False,
) -> Tuple[ImageInfo, CapacityAnalysis]:
    """Validate container image and files, then compute exact storage requirements."""
    _, image_info = image_handler.load_and_prepare_container(
        image_bytes, filename=image_filename, allow_jpeg=True
    )
    payload_files = file_manager.prepare_payload_files(files, category=category)

    # Build the exact compressed payload to know true required storage
    inner_bytes = payload_manager.serialize_inner_files(payload_files)
    compressed_bytes = payload_manager.compression_engine.compress_data(inner_bytes)
    encryption_overhead = (
        payload_manager.encryption_engine.SALT_SIZE_BYTES
        + payload_manager.encryption_engine.NONCE_SIZE_BYTES
        + 16  # AES-GCM authentication tag
        if use_encryption
        else 0
    )
    required_bytes = payload_manager.OUTER_HEADER_SIZE + len(compressed_bytes) + encryption_overhead
    available_bytes = image_info.raw_capacity_bytes
    remaining_bytes = available_bytes - required_bytes
    raw_files_size = sum(f.size for f in payload_files)

    analysis = CapacityAnalysis(
        available_bytes=available_bytes,
        required_bytes=required_bytes,
        remaining_bytes=remaining_bytes,
        fits=required_bytes <= available_bytes,
        raw_files_size_bytes=raw_files_size,
        file_count=len(payload_files),
    )
    return image_info, analysis


def encode_files_into_image(
    image_bytes: bytes,
    image_filename: str,
    files: Sequence[Tuple[str, bytes]],
    category: Optional[str] = None,
    password: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> EncodeResult:
    """Execute the complete 6-stage encoding pipeline and return a lossless PNG."""
    steps_log: List[str] = []

    def report(step_num: int, label: str) -> None:
        steps_log.append(f"{step_num}. {label}")
        if progress_callback:
            progress_callback(step_num, label)

    pixel_array, image_info = image_handler.load_and_prepare_container(
        image_bytes, filename=image_filename, allow_jpeg=True
    )
    payload_files: List[PayloadFile] = file_manager.prepare_payload_files(files, category=category)

    # Stages 1, 2, 3 happen inside pack_envelope
    envelope = payload_manager.pack_envelope(
        payload_files,
        password=password or None,
        compress=True,
        progress_callback=report,
    )

    # Strict capacity enforcement — never silently truncate
    if len(envelope) > image_info.raw_capacity_bytes:
        raise CapacityExceededError(
            f"The selected files require {format_bytes(len(envelope))} ({len(envelope):,} bytes) "
            f"after packaging, which exceeds this image's maximum capacity of "
            f"{format_bytes(image_info.raw_capacity_bytes)} ({image_info.raw_capacity_bytes:,} bytes). "
            "Please upload a higher-resolution image or select smaller files."
        )

    # Stage 4: Converting data into binary
    report(4, "Converting data into binary")
    # Stage 5: Embedding data into image
    report(5, "Embedding data into image")
    encoded_pixels = embed_bytes_into_rgb_array(pixel_array, envelope)

    # Stage 6: Generating final PNG
    report(6, "Generating final PNG")
    encoded_png_bytes = image_handler.encode_array_to_png_bytes(encoded_pixels)

    is_encrypted = bool(password)
    return EncodeResult(
        encoded_png_bytes=encoded_png_bytes,
        image_info=image_info,
        encoded_size_bytes=len(encoded_png_bytes),
        embedded_payload_bytes=len(envelope),
        raw_files_size_bytes=sum(f.size for f in payload_files),
        file_count=len(payload_files),
        filenames=[f.filename for f in payload_files],
        encrypted=is_encrypted,
        algorithm=ALGORITHM_NAME_ENCRYPTED if is_encrypted else ALGORITHM_NAME,
        steps_completed=steps_log,
    )
