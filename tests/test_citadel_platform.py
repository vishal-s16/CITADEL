"""End-to-end integration tests for the CITADEL Multi-Tool Platform."""

from __future__ import annotations

import io
import os
import unittest
import zipfile

from fastapi.testclient import TestClient
from PIL import Image

from main import app


def _make_image_bytes(width: int = 160, height: int = 120, fmt: str = "PNG") -> bytes:
    img = Image.new("RGB", (width, height), color=(24, 48, 72))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestCitadelPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_spa_routes_and_security_headers(self) -> None:
        for path in [
            "/",
            "/tools",
            "/tools/steganography",
            "/tools/docreader",
            "/tools/compressor",
            "/about",
            "/credits",
            "/contact",
            "/policy",
        ]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f"Route failed: {path}")
            self.assertIn("CITADEL", res.text)
            self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_static_assets_and_module_uis_available(self) -> None:
        assets = [
            "/assets/logos/citadel_logo.jpeg",
            "/assets/logos/citadel_intrologo.jpeg",
            "/assets/logos/favicon.png",
            "/favicon.ico",
            "/assets/music/citadel_theme.mp3",
            "/assets/music/citade_v.1.0.m.1.mp4",
            "/frontend/styles/dark-theme.css",
            "/frontend/styles/light-theme.css",
            "/frontend/styles/base.css",
            "/frontend/styles/intro.css",
            "/frontend/components/intro-overlay.js",
            "/frontend/components/music-player.js",
            "/frontend/js/router.js",
            "/frontend/pages/steganography.js",
            "/frontend/pages/docreader.js",
            "/frontend/pages/compressor.js",
            "/module-ui/docreader/",
            "/module-ui/compressor/",
            "/module-ui/compressor/services/api.js",
        ]
        for url in assets:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Asset missing: {url}")
            self.assertGreater(len(res.content), 0, f"Asset empty: {url}")

    def test_module_registry_api(self) -> None:
        health = self.client.get("/api/health").json()
        self.assertTrue(health["ok"])
        self.assertEqual(health["platform"], "CITADEL")
        self.assertEqual(health["registered_modules"], 3)

        mods_res = self.client.get("/api/modules")
        self.assertEqual(mods_res.status_code, 200)
        mods = mods_res.json()["modules"]
        self.assertEqual(len(mods), 3)
        ids = [m["module_id"] for m in mods]
        self.assertEqual(ids, ["steganography-system", "docreader", "file-compressor"])

        # Unknown module & unknown API route return clean 404 JSON
        missing_mod = self.client.get("/api/modules/does-not-exist")
        self.assertEqual(missing_mod.status_code, 404)
        self.assertFalse(missing_mod.json()["ok"])

        missing_api = self.client.get("/api/nonexistent-endpoint")
        self.assertEqual(missing_api.status_code, 404)
        self.assertFalse(missing_api.json()["ok"])

    def test_steganography_full_encrypted_multi_file_workflow(self) -> None:
        base = "/api/modules/steganography"

        # 1. Categories
        cat_res = self.client.get(f"{base}/categories")
        self.assertEqual(cat_res.status_code, 200)
        self.assertTrue(cat_res.json()["ok"])

        # 2. Analyze JPEG container
        jpeg_bytes = _make_image_bytes(200, 150, fmt="JPEG")
        ana_res = self.client.post(
            f"{base}/analyze-image",
            files={"image": ("carrier.jpg", jpeg_bytes, "image/jpeg")},
        )
        self.assertEqual(ana_res.status_code, 200)
        self.assertTrue(ana_res.json()["image"]["converted_from_jpeg"])

        # 3. Capacity analysis
        file1 = b"CITADEL secret payload #1"
        file2 = b"CITADEL secret payload #2 - integrity check"
        cap_res = self.client.post(
            f"{base}/analyze-capacity",
            files=[
                ("image", ("carrier.jpg", jpeg_bytes, "image/jpeg")),
                ("files", ("note1.txt", file1, "text/plain")),
                ("files", ("note2.txt", file2, "text/plain")),
            ],
            data={"category": "text", "use_encryption": "true"},
        )
        self.assertEqual(cap_res.status_code, 200)
        self.assertTrue(cap_res.json()["storage"]["fits"])

        # 4. Encode with AES-256-GCM password
        enc_res = self.client.post(
            f"{base}/encode",
            files=[
                ("image", ("carrier.jpg", jpeg_bytes, "image/jpeg")),
                ("files", ("note1.txt", file1, "text/plain")),
                ("files", ("note2.txt", file2, "text/plain")),
            ],
            data={
                "category": "text",
                "use_encryption": "true",
                "password": "CitadelStrongPassword!2026",
            },
        )
        self.assertEqual(enc_res.status_code, 200)
        enc_data = enc_res.json()
        self.assertTrue(enc_data["ok"])
        self.assertTrue(enc_data["encrypted"])
        self.assertEqual(enc_data["file_count"], 2)

        # 5. Download encoded PNG
        dl_res = self.client.get(enc_data["download_url"])
        self.assertEqual(dl_res.status_code, 200)
        self.assertEqual(dl_res.headers["content-type"], "image/png")
        stego_png = dl_res.content

        # 6. Inspect encoded PNG
        insp_res = self.client.post(
            f"{base}/inspect",
            files={"image": ("carrier_stego.png", stego_png, "image/png")},
        )
        self.assertEqual(insp_res.status_code, 200)
        insp_data = insp_res.json()
        self.assertTrue(insp_data["has_payload"])
        self.assertTrue(insp_data["metadata"]["is_encrypted"])
        self.assertIsNotNone(insp_data["inspect_token"])

        # 7. Wrong password rejected (401)
        bad_pwd_res = self.client.post(
            f"{base}/extract",
            files={"image": ("carrier_stego.png", stego_png, "image/png")},
            data={"password": "WrongPassword"},
        )
        self.assertEqual(bad_pwd_res.status_code, 401)
        self.assertFalse(bad_pwd_res.json()["ok"])

        # 8. Correct password extracts both files byte-for-byte via inspect_token
        ext_res = self.client.post(
            f"{base}/extract",
            data={
                "inspect_token": insp_data["inspect_token"],
                "password": "CitadelStrongPassword!2026",
            },
        )
        self.assertEqual(ext_res.status_code, 200)
        ext_data = ext_res.json()
        self.assertEqual(ext_data["file_count"], 2)
        self.assertIsNotNone(ext_data["zip_download_url"])

        f1_dl = self.client.get(ext_data["files"][0]["download_url"])
        self.assertEqual(f1_dl.status_code, 200)
        self.assertEqual(f1_dl.content, file1)

        zip_dl = self.client.get(ext_data["zip_download_url"])
        self.assertEqual(zip_dl.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(zip_dl.content)) as zf:
            self.assertEqual(zf.read("note1.txt"), file1)
            self.assertEqual(zf.read("note2.txt"), file2)

    def test_steganography_large_file_chunked_encode_and_decode(self) -> None:
        """Verify chunked LSB embedding and decoding on a multi-megabyte incompressible payload."""
        base = "/api/modules/steganography"
        # 3000x2400 RGB has ~2.7 MB raw LSB capacity; hide a 2.2 MB random binary payload
        large_carrier = _make_image_bytes(3000, 2400, fmt="JPEG")
        large_payload = os.urandom(2 * 1024 * 1024 + 200_000)

        enc_res = self.client.post(
            f"{base}/encode",
            files=[
                ("image", ("large_carrier.jpg", large_carrier, "image/jpeg")),
                ("files", ("large_blob.bin", large_payload, "application/octet-stream")),
            ],
            data={"category": "other", "use_encryption": "false"},
        )
        self.assertEqual(enc_res.status_code, 200, enc_res.text)
        enc_data = enc_res.json()
        self.assertTrue(enc_data["ok"])
        # Ensure thumbnail preview stayed lightweight instead of inlining multi-MB base64
        self.assertLess(len(enc_data["encoded_preview_data_url"]), 500_000)

        stego_png = self.client.get(enc_data["download_url"]).content

        insp_res = self.client.post(
            f"{base}/inspect",
            files={"image": ("large_stego.png", stego_png, "image/png")},
        )
        self.assertEqual(insp_res.status_code, 200, insp_res.text)
        insp_data = insp_res.json()
        self.assertTrue(insp_data["has_payload"])

        ext_res = self.client.post(
            f"{base}/extract",
            data={"inspect_token": insp_data["inspect_token"]},
        )
        self.assertEqual(ext_res.status_code, 200, ext_res.text)
        ext_data = ext_res.json()
        self.assertEqual(ext_data["file_count"], 1)

        recovered = self.client.get(ext_data["files"][0]["download_url"]).content
        self.assertEqual(recovered, large_payload)

    def test_docreader_module_end_to_end(self) -> None:
        base = "/api/modules/docreader"
        health = self.client.get(f"{base}/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        sample_text = b"CITADEL Module 02 DocReader verification document.\nSecond paragraph for search."
        up = self.client.post(
            f"{base}/documents/upload",
            files=[("files", ("citadel_test.txt", sample_text, "text/plain"))],
        )
        self.assertEqual(up.status_code, 200, up.text)
        docs = up.json()["documents"]
        self.assertEqual(len(docs), 1)
        doc_id = docs[0]["id"]

        detail = self.client.get(f"{base}/documents/{doc_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("DocReader verification", detail.json()["full_text"])

        # Cleanup uploaded test doc
        del_res = self.client.delete(f"{base}/documents/{doc_id}")
        self.assertEqual(del_res.status_code, 200)

    def test_compressor_module_end_to_end(self) -> None:
        base = "/api/modules/compressor"
        health = self.client.get(f"{base}/health")
        self.assertEqual(health.status_code, 200)

        img_bytes = _make_image_bytes(400, 300, fmt="PNG")
        up = self.client.post(
            f"{base}/upload",
            files={"file": ("sample.png", img_bytes, "image/png")},
        )
        self.assertIn(up.status_code, (200, 201), up.text)
        job_id = up.json()["job"]["jobId"]

        comp = self.client.post(
            f"{base}/compress",
            json={"jobId": job_id, "settings": {"level": "balanced"}},
        )
        self.assertEqual(comp.status_code, 200, comp.text)
        self.assertTrue(comp.json()["success"])

        dl = self.client.get(f"{base}/download/{job_id}")
        self.assertEqual(dl.status_code, 200)
        self.assertGreater(len(dl.content), 0)

        clean = self.client.delete(f"{base}/cleanup/{job_id}")
        self.assertEqual(clean.status_code, 200)

    def test_error_handling_for_plain_image_and_invalid_input(self) -> None:
        base = "/api/modules/steganography"
        plain_png = _make_image_bytes(80, 80, fmt="PNG")

        insp = self.client.post(
            f"{base}/inspect",
            files={"image": ("plain.png", plain_png, "image/png")},
        )
        self.assertEqual(insp.status_code, 200)
        self.assertFalse(insp.json()["has_payload"])

        bad_img = self.client.post(
            f"{base}/analyze-image",
            files={"image": ("fake.png", b"not-an-image", "image/png")},
        )
        self.assertEqual(bad_img.status_code, 400)
        self.assertFalse(bad_img.json()["ok"])


if __name__ == "__main__":
    unittest.main()
