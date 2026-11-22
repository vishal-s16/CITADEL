# CITADEL — Multi-Tool Web Platform

**One Platform. Multiple Possibilities.**

[![Deployed on Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black?style=for-the-badge&logo=vercel)](https://citadel-two-olive.vercel.app)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-citadel--two--olive.vercel.app-0070F3?style=for-the-badge&logo=google-chrome&logoColor=white)](https://citadel-two-olive.vercel.app)

🌐 **Live Website:** [https://citadel-two-olive.vercel.app](https://citadel-two-olive.vercel.app)

CITADEL is a centralized, modular web platform designed to host independent digital utilities and security tools under a single unified interface.

## Included Modules

- **Module 01 — Steganography System** (`/tools/steganography`)
  - Universal Image Steganography backend (`RGB LSB`, `zlib` compression, optional `AES-256-GCM` with `PBKDF2-HMAC-SHA256`, `SHA-256` + `CRC32` integrity verification, multi-file embedding & ZIP extraction).
- **Module 02 — DocReader** (`/tools/docreader`)
  - Universal Document Reader supporting PDF, Word, PowerPoint, Excel, OpenDocument, RTF, Markdown, HTML, text files, and images with full text extraction, search, and sanitization.
- **Module 03 — Universal File Compressor** (`/tools/compressor`)
  - Hybrid client-side & server-side intelligent file compression for images, PDFs, videos, audio, and documents with configurable target file size and quality preservation.


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
