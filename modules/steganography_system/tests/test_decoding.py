"""Tests for payload detection, multi-file extraction, disk persistence, and ZIP downloads."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app import app
from modules import extraction_engine, steganography_engine
from modules.exceptions import NoPayloadError
from tests.test_encoding import make_test_image


class TestDecoding(unittest.TestCase):
    def test_plain_image_reports_no_payload(self):
        plain_png = make_test_image(150, 150, fmt="PNG")
        inspection = extraction_engine.inspect_encoded_image(plain_png, "plain.png")
        self.assertFalse(inspection.has_payload)
        self.assertEqual(inspection.message, "No hidden data from this application was detected.")

        with self.assertRaises(NoPayloadError) as ctx:
            extraction_engine.extract_files_from_image(plain_png, "plain.png")
        self.assertEqual(str(ctx.exception), "No hidden data from this application was detected.")

    def test_multiple_files_round_trip_and_disk_persistence(self):
        carrier = make_test_image(400, 300, fmt="PNG")
        originals = [
            ("notes.txt", b"Line 1\nLine 2\nUnicode: \xc3\xa9\xe2\x9c\x93"),
            ("data.json", b'{"project": "stego", "count": 3, "valid": true}'),
            ("table.csv", b"id,name,score\n1,Alice,98\n2,Bob,94\n"),
        ]
        result = steganography_engine.encode_files_into_image(
            image_bytes=carrier,
            image_filename="carrier.png",
            files=originals,
            category="text",
        )

        # Save to disk and reopen as PNG to ensure persistence
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "encoded_output.png"
            out_path.write_bytes(result.encoded_png_bytes)
            reopened_bytes = out_path.read_bytes()

        extracted = extraction_engine.extract_files_from_image(reopened_bytes, "encoded_output.png")
        self.assertEqual(len(extracted.files), len(originals))
        for (orig_name, orig_data), rec in zip(originals, extracted.files):
            self.assertEqual(rec.filename, orig_name)
            self.assertEqual(rec.data, orig_data)

    def test_fastapi_inspect_extract_individual_and_zip_download(self):
        client = TestClient(app)
        carrier = make_test_image(300, 250, fmt="PNG")
        f1 = ("report.txt", b"Quarterly security report contents.")
        f2 = ("config.json", b'{"cipher": "AES-256-GCM"}')

        encoded = steganography_engine.encode_files_into_image(
            image_bytes=carrier,
            image_filename="carrier.png",
            files=[f1, f2],
            category="text",
        )

        inspect_res = client.post(
            "/api/inspect",
            files={"image": ("stego.png", encoded.encoded_png_bytes, "image/png")},
        )
        self.assertEqual(inspect_res.status_code, 200)
        self.assertTrue(inspect_res.json()["has_payload"])
        self.assertFalse(inspect_res.json()["metadata"]["is_encrypted"])

        extract_res = client.post(
            "/api/extract",
            files={"image": ("stego.png", encoded.encoded_png_bytes, "image/png")},
        )
        self.assertEqual(extract_res.status_code, 200)
        data = extract_res.json()
        self.assertEqual(data["file_count"], 2)
        self.assertIsNotNone(data["zip_download_url"])

        # Download individual file 0
        dl0 = client.get(data["files"][0]["download_url"])
        self.assertEqual(dl0.status_code, 200)
        self.assertEqual(dl0.content, f1[1])

        # Download ZIP containing both files
        zip_res = client.get(data["zip_download_url"])
        self.assertEqual(zip_res.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
            self.assertEqual(sorted(zf.namelist()), ["config.json", "report.txt"])
            self.assertEqual(zf.read("report.txt"), f1[1])
            self.assertEqual(zf.read("config.json"), f2[1])


if __name__ == "__main__":
    unittest.main()
