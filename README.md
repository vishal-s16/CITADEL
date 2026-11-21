# CITADEL — Multi-Tool Web Platform

**One Platform. Multiple Possibilities.**

CITADEL is a centralized, modular web platform designed to host independent digital utilities and security tools under a single unified interface.

## Included Module

- **Module 01 — Steganography System** (`/tools/steganography`)
  - Preserves the complete Universal Image Steganography backend (`RGB LSB`, `zlib` compression, optional `AES-256-GCM` with `PBKDF2-HMAC-SHA256`, `SHA-256` + `CRC32` integrity verification, multi-file embedding & ZIP extraction).

## Quick Start

1. Create and activate a Python 3.10+ virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the CITADEL server:
   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8000
   ```
4. Open `http://127.0.0.1:8000` in your browser.

## Running Automated Tests

Run both the CITADEL platform integration suite and the original 29 Steganography System unit tests:

```bash
python3 -m unittest discover -s tests -v
cd modules/steganography_system && python3 -m unittest discover -s tests -v
```

## Adding Future Modules

See `documentation/ARCHITECTURE.md` for step-by-step instructions on registering Module 02+ without modifying CITADEL's core architecture.
