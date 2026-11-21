"""Binary payload serialization, framing, and envelope management."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from modules import compression_engine, encryption_engine, integrity_checker
from modules.exceptions import (
    CorruptedPayloadError,
    EmptyFileSelectionError,
    NoPayloadError,
    PasswordRequiredError,
)
from modules.file_manager import PayloadFile, sanitize_filename

MAGIC_SIGNATURE = b"UISTEG01"
PAYLOAD_VERSION = 1

FLAG_COMPRESSED = 1 << 0
FLAG_ENCRYPTED = 1 << 1

# Outer envelope header layout (big-endian):
#   8s  magic signature ("UISTEG01")
#   B   version (1)
#   B   flags (bit 0: compressed, bit 1: encrypted)
#   B   salt_len (0 or 16)
#   B   nonce_len (0 or 12)
#   I   kdf_iterations (0 or e.g. 200000)
#   Q   body_len (exact byte length of salt + nonce + payload_data)
#   I   header_crc32 (CRC32 over the preceding 24 header bytes)
OUTER_HEADER_PREFIX_FMT = "!8sBBBBIQ"
OUTER_HEADER_FMT = "!8sBBBBIQI"
OUTER_HEADER_SIZE = struct.calcsize(OUTER_HEADER_FMT)  # 28 bytes

INNER_HEADER_FMT = "!I32s"  # file_count (uint32) + overall_sha256 (32 bytes)
INNER_HEADER_SIZE = struct.calcsize(INNER_HEADER_FMT)  # 36 bytes


@dataclass(frozen=True)
class EnvelopeHeader:
    """Parsed outer envelope header metadata."""

    version: int
    is_compressed: bool
    is_encrypted: bool
    salt_len: int
    nonce_len: int
    kdf_iterations: int
    body_len: int

    @property
    def total_embedded_bytes(self) -> int:
        return OUTER_HEADER_SIZE + self.body_len


@dataclass(frozen=True)
class ExtractedPayload:
    """Result of deserializing and verifying an embedded payload."""

    version: int
    is_compressed: bool
    is_encrypted: bool
    files: List[PayloadFile]
    overall_sha256_hex: str


def serialize_inner_files(files: Sequence[PayloadFile]) -> bytes:
    """Serialize one or more PayloadFile records with per-file and overall SHA-256 hashes."""
    if not files:
        raise EmptyFileSelectionError("At least one file is required to build a payload.")

    entries_chunks: List[bytes] = []
    for item in files:
        clean_name = sanitize_filename(item.filename)
        name_bytes = clean_name.encode("utf-8")
        ext_bytes = item.extension.encode("utf-8")
        if len(name_bytes) > 65535 or len(ext_bytes) > 65535:
            raise CorruptedPayloadError(f"Filename '{clean_name}' is too long to embed.")

        file_hash = integrity_checker.compute_sha256(item.data)
        entry_header = struct.pack("!HHQ32s", len(name_bytes), len(ext_bytes), len(item.data), file_hash)
        entries_chunks.append(entry_header)
        entries_chunks.append(name_bytes)
        entries_chunks.append(ext_bytes)
        entries_chunks.append(item.data)

    entries_blob = b"".join(entries_chunks)
    overall_hash = integrity_checker.compute_sha256(entries_blob)
    inner_header = struct.pack(INNER_HEADER_FMT, len(files), overall_hash)
    return inner_header + entries_blob


def deserialize_inner_files(raw_inner: bytes) -> Tuple[List[PayloadFile], str]:
    """Deserialize inner payload bytes and verify overall and per-file SHA-256 integrity."""
    if len(raw_inner) < INNER_HEADER_SIZE:
        raise CorruptedPayloadError("Embedded payload metadata is missing or truncated.")

    file_count, expected_overall_hash = struct.unpack(INNER_HEADER_FMT, raw_inner[:INNER_HEADER_SIZE])
    if file_count == 0:
        raise CorruptedPayloadError("Embedded payload contains no files.")

    entries_blob = raw_inner[INNER_HEADER_SIZE:]
    if not integrity_checker.verify_sha256(entries_blob, expected_overall_hash):
        raise CorruptedPayloadError(
            "Payload integrity verification failed. The encoded image may have been modified or corrupted."
        )

    offset = 0
    total_len = len(entries_blob)
    entry_hdr_fmt = "!HHQ32s"
    entry_hdr_size = struct.calcsize(entry_hdr_fmt)
    recovered: List[PayloadFile] = []

    for _ in range(file_count):
        if offset + entry_hdr_size > total_len:
            raise CorruptedPayloadError("Corrupted file table in hidden payload.")
        name_len, ext_len, file_size, expected_file_hash = struct.unpack(
            entry_hdr_fmt, entries_blob[offset : offset + entry_hdr_size]
        )
        offset += entry_hdr_size

        if offset + name_len + ext_len + file_size > total_len:
            raise CorruptedPayloadError("Corrupted file entry bounds in hidden payload.")

        try:
            filename = entries_blob[offset : offset + name_len].decode("utf-8")
            offset += name_len
            extension = entries_blob[offset : offset + ext_len].decode("utf-8")
            offset += ext_len
        except UnicodeDecodeError as exc:
            raise CorruptedPayloadError("Corrupted filename metadata in hidden payload.") from exc

        file_data = entries_blob[offset : offset + file_size]
        offset += file_size

        if not integrity_checker.verify_sha256(file_data, expected_file_hash):
            raise CorruptedPayloadError(
                f"Integrity check failed for extracted file '{filename}'."
            )

        recovered.append(
            PayloadFile(
                filename=sanitize_filename(filename),
                extension=extension,
                data=file_data,
            )
        )

    if offset != total_len:
        raise CorruptedPayloadError("Unexpected trailing data in embedded payload.")

    return recovered, expected_overall_hash.hex()


def pack_envelope(
    files: Sequence[PayloadFile],
    password: Optional[str] = None,
    compress: bool = True,
    kdf_iterations: int = encryption_engine.DEFAULT_KDF_ITERATIONS,
    progress_callback=None,
) -> bytes:
    """Build the complete binary envelope ready for LSB embedding."""
    if progress_callback:
        progress_callback(1, "Preparing files")
    inner_bytes = serialize_inner_files(files)

    flags = 0
    processed = inner_bytes

    if compress:
        if progress_callback:
            progress_callback(2, "Compressing files")
        processed = compression_engine.compress_data(processed)
        flags |= FLAG_COMPRESSED
    elif progress_callback:
        progress_callback(2, "Compressing files")

    salt = b""
    nonce = b""
    used_iterations = 0

    if password:
        if progress_callback:
            progress_callback(3, "Encrypting files")
        flags |= FLAG_ENCRYPTED
        # Bind version and flags as AAD so tampering with flags is detected by GCM
        aad = struct.pack("!8sBB", MAGIC_SIGNATURE, PAYLOAD_VERSION, flags)
        encrypted = encryption_engine.encrypt_data(
            processed,
            password=password,
            iterations=kdf_iterations,
            associated_data=aad,
        )
        salt = encrypted.salt
        nonce = encrypted.nonce
        used_iterations = encrypted.iterations
        body_payload = encrypted.ciphertext
    else:
        if progress_callback:
            progress_callback(3, "Encrypting files (skipped)")
        body_payload = processed

    body = salt + nonce + body_payload
    prefix = struct.pack(
        OUTER_HEADER_PREFIX_FMT,
        MAGIC_SIGNATURE,
        PAYLOAD_VERSION,
        flags,
        len(salt),
        len(nonce),
        used_iterations,
        len(body),
    )
    header_crc = zlib.crc32(prefix) & 0xFFFFFFFF
    header = prefix + struct.pack("!I", header_crc)
    return header + body


def parse_envelope_header(header_bytes: bytes) -> EnvelopeHeader:
    """Validate and parse the fixed 28-byte outer envelope header."""
    if len(header_bytes) < OUTER_HEADER_SIZE:
        raise NoPayloadError("No hidden data from this application was detected.")

    raw_hdr = header_bytes[:OUTER_HEADER_SIZE]
    magic, version, flags, salt_len, nonce_len, kdf_iterations, body_len, expected_crc = struct.unpack(
        OUTER_HEADER_FMT, raw_hdr
    )

    if magic != MAGIC_SIGNATURE:
        raise NoPayloadError("No hidden data from this application was detected.")

    actual_crc = zlib.crc32(raw_hdr[:24]) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise CorruptedPayloadError(
            "Hidden payload header is corrupted. The encoded image may have been modified."
        )

    if version != PAYLOAD_VERSION:
        raise CorruptedPayloadError(
            f"Unsupported payload version '{version}'. This application supports version {PAYLOAD_VERSION}."
        )

    is_compressed = bool(flags & FLAG_COMPRESSED)
    is_encrypted = bool(flags & FLAG_ENCRYPTED)

    if is_encrypted and (salt_len == 0 or nonce_len == 0 or body_len < salt_len + nonce_len + 16):
        raise CorruptedPayloadError("Encrypted payload header metadata is invalid or incomplete.")

    if not is_encrypted and (salt_len != 0 or nonce_len != 0):
        raise CorruptedPayloadError("Payload encryption metadata is inconsistent.")

    if body_len == 0:
        raise CorruptedPayloadError("Embedded payload body is empty.")

    return EnvelopeHeader(
        version=version,
        is_compressed=is_compressed,
        is_encrypted=is_encrypted,
        salt_len=salt_len,
        nonce_len=nonce_len,
        kdf_iterations=kdf_iterations,
        body_len=body_len,
    )


def unpack_envelope(
    header: EnvelopeHeader,
    body_bytes: bytes,
    password: Optional[str] = None,
) -> ExtractedPayload:
    """Decrypt (if encrypted), decompress (if compressed), and verify an envelope body."""
    if len(body_bytes) != header.body_len:
        raise CorruptedPayloadError(
            "Embedded payload is truncated or incomplete. The image may have been modified."
        )

    if header.is_encrypted:
        if not password:
            raise PasswordRequiredError(
                "This hidden payload is password-protected. Please enter the password to extract."
            )
        salt = body_bytes[: header.salt_len]
        nonce = body_bytes[header.salt_len : header.salt_len + header.nonce_len]
        ciphertext = body_bytes[header.salt_len + header.nonce_len :]

        flags = (FLAG_COMPRESSED if header.is_compressed else 0) | FLAG_ENCRYPTED
        aad = struct.pack("!8sBB", MAGIC_SIGNATURE, header.version, flags)
        data = encryption_engine.decrypt_data(
            ciphertext=ciphertext,
            password=password,
            salt=salt,
            nonce=nonce,
            iterations=header.kdf_iterations,
            associated_data=aad,
        )
    else:
        data = body_bytes

    if header.is_compressed:
        data = compression_engine.decompress_data(data)

    files, overall_hash_hex = deserialize_inner_files(data)
    return ExtractedPayload(
        version=header.version,
        is_compressed=header.is_compressed,
        is_encrypted=header.is_encrypted,
        files=files,
        overall_sha256_hex=overall_hash_hex,
    )
