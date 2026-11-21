"""End-to-end integration tests for the CITADEL Multi-Tool Platform."""

from __future__ import annotations

import io
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
            "/about",
            "/credits",
            "/contact",
            "/policy",
        ]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f"Route failed: {path}")
            self.assertIn("CITADEL", res.text)
            self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")

    def test_static_assets_and_media_available(self) -> None:
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
            "/frontend/js/router.js",
            "/frontend/pages/steganography.js",
        ]
        for url in assets:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Asset missing: {url}")
            self.assertGreater(len(res.content), 0, f"Asset empty: {url}")

    def test_module_registry_api(self) -> None:
        health = self.client.get("/api/health").json()
        self.assertTrue(health["ok"])
        self.assertEqual(health["platform"], "CITADEL")
        self.assertEqual(health["registered_modules"], 1)

        mods_res = self.client.get("/api/modules")
        self.assertEqual(mods_res.status_code, 200)
        mods = mods_res.json()["modules"]
        self.assertEqual(len(mods), 1)
        m = mods[0]
        self.assertEqual(m["module_id"], "steganography-system")
        self.assertEqual(m["code"], "MODULE 01")
        self.assertEqual(m["name"], "Steganography System")
        self.assertEqual(m["status"], "Available")
        self.assertEqual(m["entry_route"], "/tools/steganography")

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
        self.assertTrue(enc_data["download_url"].startswith(f"{base}/download/encoded/"))

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
        self.assertTrue(insp_res.json()["has_payload"])
        self.assertTrue(insp_res.json()["metadata"]["is_encrypted"])

        # 7. Wrong password rejected (401)
        bad_pwd_res = self.client.post(
            f"{base}/extract",
            files={"image": ("carrier_stego.png", stego_png, "image/png")},
            data={"password": "WrongPassword"},
        )
        self.assertEqual(bad_pwd_res.status_code, 401)
        self.assertFalse(bad_pwd_res.json()["ok"])

        # 8. Correct password extracts both files byte-for-byte
        ext_res = self.client.post(
            f"{base}/extract",
            files={"image": ("carrier_stego.png", stego_png, "image/png")},
            data={"password": "CitadelStrongPassword!2026"},
        )
        self.assertEqual(ext_res.status_code, 200)
        ext_data = ext_res.json()
        self.assertEqual(ext_data["file_count"], 2)
        self.assertIsNotNone(ext_data["zip_download_url"])

        # Individual file download
        f1_dl = self.client.get(ext_data["files"][0]["download_url"])
        self.assertEqual(f1_dl.status_code, 200)
        self.assertEqual(f1_dl.content, file1)

        # ZIP bundle download
        zip_dl = self.client.get(ext_data["zip_download_url"])
        self.assertEqual(zip_dl.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(zip_dl.content)) as zf:
            self.assertEqual(zf.read("note1.txt"), file1)
            self.assertEqual(zf.read("note2.txt"), file2)

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
