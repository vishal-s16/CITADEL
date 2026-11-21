"""Tests for RGB LSB encoding, capacity enforcement, JPEG conversion, and API workflow."""

from __future__ import annotations

import io
import unittest

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app import app
from modules import extraction_engine, image_handler, steganography_engine
from modules.exceptions import (
    CapacityExceededError,
    EmptyFileSelectionError,
    InvalidImageError,
    UnsupportedFileExtensionError,
    UnsupportedImageFormatError,
)


def make_test_image(width: int = 300, height: int = 200, fmt: str = "PNG") -> bytes:
    """Create a deterministic gradient test image in PNG or JPEG format."""
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)
    xv, yv = np.meshgrid(x, y)
    rgb = np.stack([xv, yv, ((xv.astype(np.uint16) + yv.astype(np.uint16)) // 2).astype(np.uint8)], axis=-1)
    img = Image.fromarray(rgb, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestEncoding(unittest.TestCase):
    def test_capacity_formula_and_units(self):
        raw = image_handler.calculate_raw_capacity(400, 300)
        self.assertEqual(raw, (400 * 300 * 3) // 8)
        units = image_handler.format_capacity_all_units(raw)
        self.assertEqual(units["bytes"], raw)
        self.assertAlmostEqual(units["kb"], round(raw / 1024, 2))
        self.assertAlmostEqual(units["mb"], round(raw / (1024 * 1024), 4))

    def test_jpeg_container_converted_to_lossless_png(self):
        jpeg_bytes = make_test_image(250, 200, fmt="JPEG")
        payload = ("secret.txt", b"Lossless PNG conversion test payload.")
        result = steganography_engine.encode_files_into_image(
            image_bytes=jpeg_bytes,
            image_filename="photo.jpg",
            files=[payload],
            category="text",
        )
        self.assertTrue(result.image_info.converted_from_jpeg)
        with Image.open(io.BytesIO(result.encoded_png_bytes)) as out_img:
            self.assertEqual(out_img.format, "PNG")
            self.assertEqual(out_img.size, (250, 200))

        extracted = extraction_engine.extract_files_from_image(result.encoded_png_bytes)
        self.assertEqual(len(extracted.files), 1)
        self.assertEqual(extracted.files[0].filename, "secret.txt")
        self.assertEqual(extracted.files[0].data, payload[1])

    def test_visual_quality_preserved_max_lsb_diff_is_one(self):
        png_bytes = make_test_image(200, 200, fmt="PNG")
        orig_arr, _ = image_handler.load_and_prepare_container(png_bytes, "orig.png")
        result = steganography_engine.encode_files_into_image(
            image_bytes=png_bytes,
            image_filename="orig.png",
            files=[("notes.txt", b"Steganography visual fidelity check " * 50)],
            category="text",
        )
        enc_arr, _ = image_handler.load_and_prepare_container(result.encoded_png_bytes, "enc.png")
        max_diff = int(np.max(np.abs(orig_arr.astype(np.int16) - enc_arr.astype(np.int16))))
        self.assertLessEqual(max_diff, 1)

    def test_capacity_exceeded_rejected_without_truncation(self):
        tiny_png = make_test_image(30, 30, fmt="PNG")  # Raw capacity = 337 bytes
        incompressible_blob = bytes(np.random.default_rng(42).integers(0, 256, size=2048, dtype=np.uint8))

        _, analysis = steganography_engine.analyze_storage_capacity(
            image_bytes=tiny_png,
            image_filename="tiny.png",
            files=[("big.bin", incompressible_blob)],
            category="other",
        )
        self.assertFalse(analysis.fits)

        with self.assertRaises(CapacityExceededError):
            steganography_engine.encode_files_into_image(
                image_bytes=tiny_png,
                image_filename="tiny.png",
                files=[("big.bin", incompressible_blob)],
                category="other",
            )

    def test_progress_callback_reports_all_six_steps(self):
        png_bytes = make_test_image(150, 150, fmt="PNG")
        seen_steps = []
        steganography_engine.encode_files_into_image(
            image_bytes=png_bytes,
            image_filename="carrier.png",
            files=[("hello.txt", b"hello world")],
            category="text",
            progress_callback=lambda step, label: seen_steps.append((step, label)),
        )
        self.assertEqual([s for s, _ in seen_steps], [1, 2, 3, 4, 5, 6])

    def test_validation_errors(self):
        png_bytes = make_test_image(100, 100, fmt="PNG")

        with self.assertRaises(InvalidImageError):
            image_handler.load_and_prepare_container(b"not an image", "bad.png")

        gif_buf = io.BytesIO()
        Image.new("RGB", (50, 50), color=(10, 20, 30)).save(gif_buf, format="GIF")
        with self.assertRaises(UnsupportedImageFormatError):
            image_handler.load_and_prepare_container(gif_buf.getvalue(), "anim.gif")

        with self.assertRaises(EmptyFileSelectionError):
            steganography_engine.encode_files_into_image(png_bytes, "c.png", [], category="text")

        with self.assertRaises(UnsupportedFileExtensionError):
            steganography_engine.encode_files_into_image(
                png_bytes, "c.png", [("script.py", b"print(1)")], category="text"
            )

    def test_fastapi_end_to_end_encode_and_download(self):
        client = TestClient(app)
        home = client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn("Image Steganography", home.text)

        cats = client.get("/api/categories")
        self.assertEqual(cats.status_code, 200)
        self.assertEqual(len(cats.json()["categories"]), 8)

        png_bytes = make_test_image(200, 200, fmt="PNG")
        analyze_res = client.post(
            "/api/analyze-image",
            files={"image": ("carrier.png", png_bytes, "image/png")},
        )
        self.assertEqual(analyze_res.status_code, 200)
        self.assertEqual(analyze_res.json()["image"]["width"], 200)

        encode_res = client.post(
            "/api/encode",
            data={"category": "text", "use_encryption": "false"},
            files=[
                ("image", ("carrier.png", png_bytes, "image/png")),
                ("files", ("alpha.txt", b"Alpha content 123", "text/plain")),
            ],
        )
        self.assertEqual(encode_res.status_code, 200)
        body = encode_res.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["file_count"], 1)

        dl_res = client.get(body["download_url"])
        self.assertEqual(dl_res.status_code, 200)
        self.assertEqual(dl_res.headers["content-type"], "image/png")

        extracted = extraction_engine.extract_files_from_image(dl_res.content)
        self.assertEqual(extracted.files[0].filename, "alpha.txt")
        self.assertEqual(extracted.files[0].data, b"Alpha content 123")


if __name__ == "__main__":
    unittest.main()
