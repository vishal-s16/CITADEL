"""Tests covering all required file formats: small/large TXT, PDF, ZIP, PNG, JPG, MP3, MP4, code, and other."""

from __future__ import annotations

import io
import unittest
import zipfile

import numpy as np

from modules import extraction_engine, steganography_engine
from tests.test_encoding import make_test_image


def make_sample_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
        b"trailer << /Root 1 0 R >>\n%%EOF\n"
    )


def make_sample_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", "Inside nested archive")
        zf.writestr("data.json", '{"nested": true}')
    return buf.getvalue()


def make_sample_mp3_bytes() -> bytes:
    # ID3v2 header + MPEG audio frame sync pattern + deterministic payload bytes
    rng = np.random.default_rng(101)
    id3 = b"ID3\x03\x00\x00\x00\x00\x00\x0a" + b"\x00" * 10
    frames = b"\xff\xfb\x90\x00" + bytes(rng.integers(0, 256, size=4096, dtype=np.uint8))
    return id3 + frames


def make_sample_mp4_bytes() -> bytes:
    # ISO BMFF ftyp box + mdat box with deterministic binary media bytes
    rng = np.random.default_rng(202)
    ftyp = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"
    mdat_body = bytes(rng.integers(0, 256, size=8192, dtype=np.uint8))
    mdat_size = (8 + len(mdat_body)).to_bytes(4, "big")
    return ftyp + mdat_size + b"mdat" + mdat_body


class TestFileFormats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 800 x 600 RGB image => 180,000 bytes (~175.8 KB) raw capacity
        cls.large_carrier = make_test_image(800, 600, fmt="PNG")

    def _assert_round_trip(self, filename: str, content: bytes, category: str, expected_ext: str):
        encoded = steganography_engine.encode_files_into_image(
            image_bytes=self.large_carrier,
            image_filename="carrier.png",
            files=[(filename, content)],
            category=category,
        )
        extracted = extraction_engine.extract_files_from_image(encoded.encoded_png_bytes)
        self.assertEqual(len(extracted.files), 1)
        rec = extracted.files[0]
        self.assertEqual(rec.filename, filename)
        self.assertEqual(rec.extension, expected_ext)
        self.assertEqual(rec.data, content)

    def test_small_txt_file(self):
        self._assert_round_trip("small.txt", b"Short message hidden inside PNG.", "text", "txt")

    def test_large_txt_file(self):
        # ~120 KB text file (compresses cleanly well under 180 KB capacity)
        large_text = ("Universal Image Steganography test line 0123456789.\n" * 2400).encode("utf-8")
        self.assertGreater(len(large_text), 100_000)
        self._assert_round_trip("large_log.txt", large_text, "text", "txt")

    def test_pdf_document(self):
        self._assert_round_trip("contract.pdf", make_sample_pdf_bytes(), "documents", "pdf")

    def test_zip_archive(self):
        self._assert_round_trip("bundle.zip", make_sample_zip_bytes(), "archives", "zip")

    def test_png_image_payload(self):
        nested_png = make_test_image(64, 64, fmt="PNG")
        self._assert_round_trip("icon.png", nested_png, "images", "png")

    def test_jpg_image_payload(self):
        nested_jpg = make_test_image(80, 60, fmt="JPEG")
        self._assert_round_trip("thumbnail.jpg", nested_jpg, "images", "jpg")

    def test_mp3_audio_payload(self):
        self._assert_round_trip("clip.mp3", make_sample_mp3_bytes(), "audio", "mp3")

    def test_mp4_video_payload(self):
        self._assert_round_trip("sample.mp4", make_sample_mp4_bytes(), "video", "mp4")

    def test_programming_files(self):
        code = b"def greet(name: str) -> str:\n    return f'Hello, {name}!'\n"
        self._assert_round_trip("helper.py", code, "programming", "py")

    def test_multiple_heterogeneous_files_under_other_category(self):
        files = [
            ("notes.txt", b"Plain text note"),
            ("doc.pdf", make_sample_pdf_bytes()),
            ("archive.zip", make_sample_zip_bytes()),
            ("clip.mp3", make_sample_mp3_bytes()),
            ("video.mp4", make_sample_mp4_bytes()),
            ("custom.dat", b"\x00\x01\x02\xfe\xffcustom binary"),
        ]
        encoded = steganography_engine.encode_files_into_image(
            image_bytes=self.large_carrier,
            image_filename="carrier.png",
            files=files,
            category="other",
            password="MultiFilePassword!2026",
        )
        extracted = extraction_engine.extract_files_from_image(
            encoded.encoded_png_bytes, password="MultiFilePassword!2026"
        )
        self.assertEqual(len(extracted.files), len(files))
        for (orig_name, orig_bytes), rec in zip(files, extracted.files):
            self.assertEqual(rec.filename, orig_name)
            self.assertEqual(rec.data, orig_bytes)


if __name__ == "__main__":
    unittest.main()
