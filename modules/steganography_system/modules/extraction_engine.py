"""RGB Least Significant Bit (LSB) steganography detection and extraction engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from modules import image_handler, payload_manager
from modules.exceptions import CorruptedPayloadError, NoPayloadError
from modules.file_manager import PayloadFile
from modules.image_handler import ImageInfo
from modules.payload_manager import EnvelopeHeader


@dataclass(frozen=True)
class InspectionResult:
    """Metadata detected from an encoded PNG without decrypting the body."""

    has_payload: bool
    image_info: ImageInfo
    header: Optional[EnvelopeHeader]
    message: str

    def to_dict(self) -> dict:
        return {
            "has_payload": self.has_payload,
            "message": self.message,
            "image": self.image_info.to_dict(),
            "metadata": {
                "version": self.header.version,
                "is_compressed": self.header.is_compressed,
                "is_encrypted": self.header.is_encrypted,
                "embedded_bytes": self.header.total_embedded_bytes,
            }
            if self.header
            else None,
        }


@dataclass(frozen=True)
class ExtractionResult:
    """Complete result from extracting and verifying hidden files."""

    image_info: ImageInfo
    version: int
    is_compressed: bool
    is_encrypted: bool
    files: List[PayloadFile]
    overall_sha256_hex: str


def extract_bytes_from_rgb_array(
    pixel_array: np.ndarray,
    byte_offset: int,
    num_bytes: int,
) -> bytes:
    """Extract an exact slice of bytes from the LSBs of pixel_array."""
    if byte_offset < 0 or num_bytes < 0:
        raise CorruptedPayloadError("Invalid extraction bounds.")

    flat_pixels = pixel_array.reshape(-1)
    start_bit = byte_offset * 8
    end_bit = (byte_offset + num_bytes) * 8

    if end_bit > flat_pixels.size:
        raise CorruptedPayloadError(
            "Declared payload size exceeds the image's pixel capacity. "
            "The encoded image may have been cropped or corrupted."
        )

    bits = flat_pixels[start_bit:end_bit] & np.uint8(1)
    return np.packbits(bits, bitorder="big").tobytes()


def inspect_encoded_image(
    image_bytes: bytes,
    image_filename: str = "encoded.png",
) -> InspectionResult:
    """Inspect a PNG image to detect whether a supported application payload is present."""
    pixel_array, image_info = image_handler.load_and_prepare_container(
        image_bytes, filename=image_filename, allow_jpeg=False
    )

    if image_info.raw_capacity_bytes < payload_manager.OUTER_HEADER_SIZE:
        return InspectionResult(
            has_payload=False,
            image_info=image_info,
            header=None,
            message="No hidden data from this application was detected.",
        )

    header_bytes = extract_bytes_from_rgb_array(
        pixel_array, byte_offset=0, num_bytes=payload_manager.OUTER_HEADER_SIZE
    )
    try:
        header = payload_manager.parse_envelope_header(header_bytes)
    except NoPayloadError:
        return InspectionResult(
            has_payload=False,
            image_info=image_info,
            header=None,
            message="No hidden data from this application was detected.",
        )

    if header.total_embedded_bytes > image_info.raw_capacity_bytes:
        raise CorruptedPayloadError(
            "Hidden payload length exceeds image bounds. The encoded image appears corrupted or cropped."
        )

    return InspectionResult(
        has_payload=True,
        image_info=image_info,
        header=header,
        message=(
            "Encrypted hidden payload detected. Enter the password to extract."
            if header.is_encrypted
            else "Hidden payload detected and ready for extraction."
        ),
    )


def extract_files_from_image(
    image_bytes: bytes,
    image_filename: str = "encoded.png",
    password: Optional[str] = None,
) -> ExtractionResult:
    """Detect, decrypt (if needed), decompress, verify, and reconstruct hidden files."""
    pixel_array, image_info = image_handler.load_and_prepare_container(
        image_bytes, filename=image_filename, allow_jpeg=False
    )

    if image_info.raw_capacity_bytes < payload_manager.OUTER_HEADER_SIZE:
        raise NoPayloadError("No hidden data from this application was detected.")

    header_bytes = extract_bytes_from_rgb_array(
        pixel_array, byte_offset=0, num_bytes=payload_manager.OUTER_HEADER_SIZE
    )
    header = payload_manager.parse_envelope_header(header_bytes)

    if header.total_embedded_bytes > image_info.raw_capacity_bytes:
        raise CorruptedPayloadError(
            "Declared payload size exceeds the image's capacity. The encoded image may be modified or corrupted."
        )

    body_bytes = extract_bytes_from_rgb_array(
        pixel_array,
        byte_offset=payload_manager.OUTER_HEADER_SIZE,
        num_bytes=header.body_len,
    )
    extracted = payload_manager.unpack_envelope(header, body_bytes, password=password or None)

    return ExtractionResult(
        image_info=image_info,
        version=extracted.version,
        is_compressed=extracted.is_compressed,
        is_encrypted=extracted.is_encrypted,
        files=extracted.files,
        overall_sha256_hex=extracted.overall_sha256_hex,
    )
