"""Image loading, validation, format conversion, and capacity calculations."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image, UnidentifiedImageError

from modules.exceptions import InvalidImageError, UnsupportedImageFormatError

SUPPORTED_INPUT_FORMATS = {"PNG", "JPEG", "JPG"}
# Reserve bytes for outer envelope header (28B) + salt (16B) + nonce (12B) + GCM tag (16B)
# + inner payload header (36B) = 108 bytes minimum baseline metadata reservation
BASE_METADATA_RESERVE_BYTES = 128


@dataclass(frozen=True)
class ImageInfo:
    """Metadata and capacity metrics for a validated container image."""

    filename: str
    original_format: str
    width: int
    height: int
    original_size_bytes: int
    converted_from_jpeg: bool
    raw_capacity_bytes: int
    usable_capacity_bytes: int

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "original_format": self.original_format,
            "width": self.width,
            "height": self.height,
            "dimensions": f"{self.width} × {self.height}",
            "original_size_bytes": self.original_size_bytes,
            "original_size_formatted": format_bytes(self.original_size_bytes),
            "converted_from_jpeg": self.converted_from_jpeg,
            "raw_capacity_bytes": self.raw_capacity_bytes,
            "usable_capacity_bytes": self.usable_capacity_bytes,
            "capacity": format_capacity_all_units(self.raw_capacity_bytes),
            "usable_capacity": format_capacity_all_units(self.usable_capacity_bytes),
        }


def format_bytes(num_bytes: int) -> str:
    """Return a human-readable size string."""
    if num_bytes < 1024:
        return f"{num_bytes:,} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.2f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def format_capacity_all_units(num_bytes: int) -> dict:
    """Return capacity represented in Bytes, KB, and MB."""
    safe_bytes = max(0, int(num_bytes))
    return {
        "bytes": safe_bytes,
        "kb": round(safe_bytes / 1024, 2),
        "mb": round(safe_bytes / (1024 * 1024), 4),
    }


def calculate_raw_capacity(width: int, height: int) -> int:
    """Calculate raw RGB LSB storage capacity in bytes: (W * H * 3) // 8."""
    if width <= 0 or height <= 0:
        raise InvalidImageError("Image dimensions must be positive.")
    return (width * height * 3) // 8


def load_and_prepare_container(
    image_bytes: bytes,
    filename: str = "image.png",
    allow_jpeg: bool = True,
) -> Tuple[np.ndarray, ImageInfo]:
    """Validate an uploaded image, convert JPEG/non-RGB to lossless RGB array, and compute capacity."""
    if not image_bytes:
        raise InvalidImageError("Uploaded image file is empty.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidImageError(
            "The uploaded file is not a valid or readable image."
        ) from exc

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            fmt = (img.format or "").upper()
            allowed = SUPPORTED_INPUT_FORMATS if allow_jpeg else {"PNG"}
            if fmt not in allowed:
                if not allow_jpeg:
                    raise UnsupportedImageFormatError(
                        f"Unsupported image format '{fmt or 'UNKNOWN'}'. "
                        "Encoded images must be lossless PNG files."
                    )
                raise UnsupportedImageFormatError(
                    f"Unsupported image format '{fmt or 'UNKNOWN'}'. "
                    "Please upload a PNG or JPEG/JPG image."
                )

            converted_from_jpeg = fmt in {"JPEG", "JPG"}
            # Ensure lossless RGB representation for 3-channel LSB embedding
            rgb_image = img.convert("RGB")
            width, height = rgb_image.size
            pixel_array = np.array(rgb_image, dtype=np.uint8)
    except UnsupportedImageFormatError:
        raise
    except MemoryError as exc:
        raise InvalidImageError(
            "Insufficient memory to process this image. Please try a smaller image."
        ) from exc
    except (OSError, ValueError) as exc:
        raise InvalidImageError(
            "The image appears to be corrupted and could not be decoded."
        ) from exc

    raw_capacity = calculate_raw_capacity(width, height)
    usable_capacity = max(0, raw_capacity - BASE_METADATA_RESERVE_BYTES)

    info = ImageInfo(
        filename=filename,
        original_format=fmt,
        width=width,
        height=height,
        original_size_bytes=len(image_bytes),
        converted_from_jpeg=converted_from_jpeg,
        raw_capacity_bytes=raw_capacity,
        usable_capacity_bytes=usable_capacity,
    )
    return pixel_array, info


def encode_array_to_png_bytes(pixel_array: np.ndarray) -> bytes:
    """Serialize an RGB uint8 NumPy array into lossless PNG bytes."""
    if pixel_array.ndim != 3 or pixel_array.shape[2] != 3 or pixel_array.dtype != np.uint8:
        raise InvalidImageError("Internal error: pixel buffer must be an RGB uint8 array.")

    try:
        img = Image.fromarray(pixel_array, mode="RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=False)
        return buf.getvalue()
    except MemoryError as exc:
        raise InvalidImageError(
            "Insufficient memory while generating the final PNG image."
        ) from exc
    except OSError as exc:
        raise InvalidImageError("Failed to generate the final PNG image.") from exc
