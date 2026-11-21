"""AES-256-GCM authenticated encryption with PBKDF2-HMAC-SHA256 key derivation."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from modules.exceptions import DecryptionError, EncryptionError

SALT_SIZE_BYTES = 16
NONCE_SIZE_BYTES = 12
KEY_SIZE_BYTES = 32  # 256-bit AES key
DEFAULT_KDF_ITERATIONS = 200_000


@dataclass(frozen=True)
class EncryptedBlob:
    """Container for AES-256-GCM ciphertext and its non-secret metadata."""

    ciphertext: bytes
    salt: bytes
    nonce: bytes
    iterations: int


def derive_key(password: str, salt: bytes, iterations: int = DEFAULT_KDF_ITERATIONS) -> bytes:
    """Derive a 256-bit encryption key from a user password and random salt."""
    if not password:
        raise EncryptionError("Password cannot be empty when encryption is enabled.")
    if not salt:
        raise EncryptionError("Encryption salt is missing.")
    if iterations < 10_000:
        raise EncryptionError("Key derivation iteration count is too low.")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE_BYTES,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_data(
    plaintext: bytes,
    password: str,
    iterations: int = DEFAULT_KDF_ITERATIONS,
    associated_data: bytes | None = None,
) -> EncryptedBlob:
    """Encrypt plaintext bytes using AES-256-GCM with a random salt and nonce."""
    if not password:
        raise EncryptionError("Please enter a password to enable encryption.")

    salt = os.urandom(SALT_SIZE_BYTES)
    nonce = os.urandom(NONCE_SIZE_BYTES)
    key = derive_key(password, salt, iterations=iterations)

    try:
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    except Exception as exc:
        raise EncryptionError("Failed to encrypt payload data.") from exc

    return EncryptedBlob(
        ciphertext=ciphertext,
        salt=salt,
        nonce=nonce,
        iterations=iterations,
    )


def decrypt_data(
    ciphertext: bytes,
    password: str,
    salt: bytes,
    nonce: bytes,
    iterations: int,
    associated_data: bytes | None = None,
) -> bytes:
    """Decrypt AES-256-GCM ciphertext. Raises DecryptionError on wrong password or tampering."""
    if not password:
        raise DecryptionError("Incorrect password or corrupted hidden data.")

    try:
        key = derive_key(password, salt, iterations=iterations)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data)
    except (InvalidTag, EncryptionError, ValueError) as exc:
        raise DecryptionError("Incorrect password or corrupted hidden data.") from exc
