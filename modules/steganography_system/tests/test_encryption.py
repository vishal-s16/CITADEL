"""Tests for AES-256-GCM encryption, PBKDF2 key derivation, and wrong-password handling."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app import app
from modules import encryption_engine, extraction_engine, steganography_engine
from modules.exceptions import DecryptionError, PasswordRequiredError
from tests.test_encoding import make_test_image


class TestEncryption(unittest.TestCase):
    def test_encrypt_decrypt_round_trip_and_unique_salt_nonce(self):
        plaintext = b"Top secret binary payload 0123456789"
        password = "Correct-Horse-Battery-Staple!99"

        blob1 = encryption_engine.encrypt_data(plaintext, password, iterations=20_000)
        blob2 = encryption_engine.encrypt_data(plaintext, password, iterations=20_000)

        self.assertNotEqual(blob1.salt, blob2.salt)
        self.assertNotEqual(blob1.nonce, blob2.nonce)
        self.assertNotEqual(blob1.ciphertext, blob2.ciphertext)
        self.assertNotIn(password.encode("utf-8"), blob1.ciphertext)

        decrypted = encryption_engine.decrypt_data(
            ciphertext=blob1.ciphertext,
            password=password,
            salt=blob1.salt,
            nonce=blob1.nonce,
            iterations=blob1.iterations,
        )
        self.assertEqual(decrypted, plaintext)

    def test_wrong_password_raises_expected_message(self):
        carrier = make_test_image(240, 180, fmt="PNG")
        secret_file = ("vault.txt", b"Confidential key material")

        encoded = steganography_engine.encode_files_into_image(
            image_bytes=carrier,
            image_filename="vault.png",
            files=[secret_file],
            category="text",
            password="MyStrongPassword!2026",
        )
        self.assertTrue(encoded.encrypted)

        with self.assertRaises(PasswordRequiredError):
            extraction_engine.extract_files_from_image(encoded.encoded_png_bytes)

        with self.assertRaises(DecryptionError) as ctx:
            extraction_engine.extract_files_from_image(
                encoded.encoded_png_bytes, password="WrongPassword"
            )
        self.assertEqual(str(ctx.exception), "Incorrect password or corrupted hidden data.")

        recovered = extraction_engine.extract_files_from_image(
            encoded.encoded_png_bytes, password="MyStrongPassword!2026"
        )
        self.assertTrue(recovered.is_encrypted)
        self.assertEqual(recovered.files[0].filename, "vault.txt")
        self.assertEqual(recovered.files[0].data, secret_file[1])

    def test_encrypted_fastapi_workflow(self):
        client = TestClient(app)
        carrier = make_test_image(220, 180, fmt="PNG")
        pwd = "SecurePass#42"

        enc_res = client.post(
            "/api/encode",
            data={"category": "text", "use_encryption": "true", "password": pwd},
            files=[
                ("image", ("cover.png", carrier, "image/png")),
                ("files", ("keys.json", b'{"token": "xyz-987"}', "application/json")),
            ],
        )
        self.assertEqual(enc_res.status_code, 200)
        stego_png = client.get(enc_res.json()["download_url"]).content

        insp = client.post("/api/inspect", files={"image": ("s.png", stego_png, "image/png")})
        self.assertEqual(insp.status_code, 200)
        self.assertTrue(insp.json()["metadata"]["is_encrypted"])

        bad_ext = client.post(
            "/api/extract",
            data={"password": "incorrect"},
            files={"image": ("s.png", stego_png, "image/png")},
        )
        self.assertEqual(bad_ext.status_code, 401)
        self.assertEqual(bad_ext.json()["message"], "Incorrect password or corrupted hidden data.")

        good_ext = client.post(
            "/api/extract",
            data={"password": pwd},
            files={"image": ("s.png", stego_png, "image/png")},
        )
        self.assertEqual(good_ext.status_code, 200)
        dl = client.get(good_ext.json()["files"][0]["download_url"])
        self.assertEqual(dl.content, b'{"token": "xyz-987"}')


if __name__ == "__main__":
    unittest.main()
