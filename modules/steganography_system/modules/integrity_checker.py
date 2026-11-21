"""SHA-256 integrity hashing and constant-time verification."""

from __future__ import annotations

import hashlib
import hmac

SHA256_DIGEST_SIZE = 32


def compute_sha256(data: bytes) -> bytes:
    """Compute raw 32-byte SHA-256 digest of data."""
    return hashlib.sha256(data).digest()


def compute_sha256_hex(data: bytes) -> str:
    """Compute hex-encoded SHA-256 digest of data."""
    return hashlib.sha256(data).hexdigest()


def verify_sha256(data: bytes, expected_digest: bytes) -> bool:
    """Verify data against an expected 32-byte SHA-256 digest in constant time."""
    if not isinstance(expected_digest, (bytes, bytearray)) or len(expected_digest) != SHA256_DIGEST_SIZE:
        return False
    actual = hashlib.sha256(data).digest()
    return hmac.compare_digest(actual, expected_digest)
