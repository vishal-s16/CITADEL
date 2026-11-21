# Universal Image Steganography Application

A modern, full-stack web application that hides any digital file (or multiple files) inside ordinary PNG or JPEG images using lossless **RGB Least Significant Bit (LSB)** steganography, **zlib** compression, **SHA-256** integrity verification, and optional **AES-256-GCM** password-based encryption.

## Architecture

```
universal_image_steganography/
├── app.py                        # FastAPI backend server & REST API
├── requirements.txt              # Python dependencies
├── README.md                     # Setup, usage, and architecture guide
├── modules/
│   ├── exceptions.py             # Structured user-facing exception types
│   ├── image_handler.py          # PNG/JPEG validation, lossless conversion, capacity math
│   ├── file_manager.py           # 8 file categories, extension validation, ZIP packaging
│   ├── compression_engine.py     # zlib compression & decompression
│   ├── encryption_engine.py      # PBKDF2-HMAC-SHA256 + AES-256-GCM encryption
│   ├── integrity_checker.py      # SHA-256 hashing & constant-time verification
│   ├── payload_manager.py        # Binary framing, magic signature, CRC32 header, serialization
│   ├── steganography_engine.py   # Vectorized RGB LSB embedding & capacity analysis
│   └── extraction_engine.py      # Payload detection, decryption, verification & extraction
├── frontend/
│   ├── templates/index.html      # Main dark-themed HTML shell
│   ├── components/               # Modular UI components (Stages 1–3, Result, Extract)
│   └── static/
│       ├── css/style.css         # Responsive dark-themed styling
│       └── js/app.js             # Frontend workflow controller
└── tests/
    ├── test_encoding.py          # Encoding, capacity enforcement, JPEG-to-PNG, API tests
    ├── test_decoding.py          # Detection, multi-file extraction, ZIP bundle, persistence
    ├── test_encryption.py        # AES-256-GCM round-trips, wrong password, salt/nonce uniqueness
    ├── test_integrity.py         # Header CRC32, pixel tampering, SHA-256 & truncation checks
    └── test_file_formats.py      # TXT, large TXT, PDF, ZIP, PNG, JPG, MP3, MP4, programming & other
```

## Binary Payload Structure

Every encoded PNG embeds a self-describing binary envelope starting at bit 0 of the RGB pixel stream (no fragile end-marker):

1. **Fixed Outer Header (28 bytes, big-endian)**:
   - `8 bytes`: Magic signature (`UISTEG01`)
   - `1 byte`: Payload version (`1`)
   - `1 byte`: Flags (`bit 0`: zlib compressed, `bit 1`: AES-256-GCM encrypted)
   - `1 byte`: Salt length (`0` or `16`)
   - `1 byte`: Nonce length (`0` or `12`)
   - `4 bytes`: PBKDF2 iteration count (`0` or `200000`)
   - `8 bytes`: Exact body length in bytes (`uint64`)
   - `4 bytes`: CRC32 checksum over the first 24 header bytes
2. **Envelope Body**:
   - Optional `16-byte` random salt + `12-byte` random nonce
   - Compressed (and optionally AES-256-GCM encrypted) inner payload containing file count, overall SHA-256 digest, and per-file metadata (`filename`, `extension`, `size`, `file_sha256`, and raw bytes).

## Installation

1. Ensure **Python 3.10+** is installed.
2. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Start the FastAPI server with Uvicorn:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

Then open your browser to:

```
http://127.0.0.1:8000
```

## Running the Test Suite

Run all automated tests from the project root directory:

```bash
python3 -m unittest discover -s tests -v
```

## Capacity Formula & Known Limitations

- **RGB LSB Capacity**: `(Image Width × Image Height × 3) / 8` bytes, minus header and metadata overhead.
- **Lossless Transport Required**: Encoded images are saved as lossless PNGs. Re-compressing an encoded PNG as JPEG, resizing it, or sharing it through messaging apps that re-encode images will destroy the LSB data.
- **In-Memory Download Cache**: Generated encoded PNGs and extracted file sessions are kept in a bounded in-memory cache (1-hour TTL, max 20 sessions) so sensitive files are never written in plaintext to disk; restarting the server clears active download links.
- **Detection Scope**: The extraction engine detects payloads created with this application's `UISTEG01` envelope signature; it does not attempt to detect arbitrary third-party steganography tools.
