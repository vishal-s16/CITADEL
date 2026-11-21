"""Tests for SHA-256 integrity verification, header CRC32, tampering, and corruption detection."""

from __future__ import annotations

import io
import unittest

import numpy as np
from PIL import Image

from modules import extraction_engine, image_handler, integrity_checker, steganography_engine
from modules.exceptions import (
    CompressionError,
    CorruptedPayloadError,
    DecryptionError,
    NoPayloadError,
    UnsupportedImageFormatError,
)
from tests.test_encoding import make_test_image


class TestIntegrity(unittest.TestCase):
    def test_sha256_verification(self):
        data = b"Integrity check payload"
        digest = integrity_checker.compute_sha256(data)
        self.assertTrue(integrity_checker.verify_sha256(data, digest))
        self.assertFalse(integrity_checker.verify_sha256(data + b"!", digest))
        self.assertFalse(integrity_checker.verify_sha256(data, b"short"))

    def test_corrupted_header_detected_by_crc32(self):
        carrier = make_test_image(200, 200, fmt="PNG")
        encoded = steganography_engine.encode_files_into_image(
            carrier, "c.png", [("doc.txt", b"Important content")], category="text"
        )
        arr, _ = image_handler.load_and_prepare_container(encoded.encoded_png_bytes, "e.png")
        # Flip an LSB inside header bytes (byte 10, after the 8-byte magic signature)
        flat = arr.reshape(-1)
        flat[10 * 8] ^= np.uint8(1)
        corrupted_png = image_handler.encode_array_to_png_bytes(flat.reshape(arr.shape))

        with self.assertRaises(CorruptedPayloadError):
            extraction_engine.extract_files_from_image(corrupted_png)

    def test_corrupted_payload_body_detected(self):
        carrier = make_test_image(200, 200, fmt="PNG")
        encoded = steganography_engine.encode_files_into_image(
            carrier, "c.png", [("doc.txt", b"Payload body tamper test " * 20)], category="text"
        )
        arr, _ = image_handler.load_and_prepare_container(encoded.encoded_png_bytes, "e.png")
        flat = arr.reshape(-1)
        # Flip several LSBs in the compressed body (past 28-byte header = bit 224)
        for bit_idx in range(260, 280):
            flat[bit_idx] ^= np.uint8(1)
        tampered_png = image_handler.encode_array_to_png_bytes(flat.reshape(arr.shape))

        with self.assertRaises((CorruptedPayloadError, CompressionError)):
            extraction_engine.extract_files_from_image(tampered_png)

    def test_corrupted_encrypted_payload_detected_by_gcm_tag(self):
        carrier = make_test_image(200, 200, fmt="PNG")
        encoded = steganography_engine.encode_files_into_image(
            carrier,
            "c.png",
            [("secret.txt", b"Authenticated encryption integrity check")],
            category="text",
            password="StrongPassword123",
        )
        arr, _ = image_handler.load_and_prepare_container(encoded.encoded_png_bytes, "e.png")
        flat = arr.reshape(-1)
        # Flip 1 bit inside the encrypted ciphertext
        flat[60 * 8] ^= np.uint8(1)
        tampered_png = image_handler.encode_array_to_png_bytes(flat.reshape(arr.shape))

        with self.assertRaises(DecryptionError):
            extraction_engine.extract_files_from_image(tampered_png, password="StrongPassword123")

    def test_cropped_encoded_image_rejected(self):
        carrier = make_test_image(250, 250, fmt="PNG")
        data = bytes(np.random.default_rng(7).integers(0, 256, size=8000, dtype=np.uint8))
        encoded = steganography_engine.encode_files_into_image(
            carrier, "c.png", [("blob.bin", data)], category="other"
        )
        with Image.open(io.BytesIO(encoded.encoded_png_bytes)) as img:
            cropped = img.crop((0, 0, 50, 50))
            buf = io.BytesIO()
            cropped.save(buf, format="PNG")
            cropped_bytes = buf.getvalue()

        with self.assertRaises((CorruptedPayloadError, NoPayloadError)):
            extraction_engine.extract_files_from_image(cropped_bytes)

    def test_recompressed_as_jpeg_rejected_for_extraction(self):
        carrier = make_test_image(150, 150, fmt="PNG")
        encoded = steganography_engine.encode_files_into_image(
            carrier, "c.png", [("note.txt", b"Hello")], category="text"
        )
        with Image.open(io.BytesIO(encoded.encoded_png_bytes)) as img:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            jpeg_bytes = buf.getvalue()

        with self.assertRaises(UnsupportedImageFormatError):
            extraction_engine.extract_files_from_image(jpeg_bytes, "recompressed.jpg")


if __name__ == "__main__":
    unittest.main()
