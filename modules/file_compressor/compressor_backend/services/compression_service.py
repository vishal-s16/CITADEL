"""Core compression engine supporting PDF, JPG/JPEG, PNG, WEBP, MP4, MOV, DOCX, PPTX, and ZIP."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter

from ..utils.file_cleanup import cleanup_job_directory, safe_delete_file

MAX_ARCHIVE_ENTRIES = 5000
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB Zip-Bomb ceiling

# In-memory temporary job registry (never permanently stores user files)
_JOBS: dict[str, dict[str, Any]] = {}


def _find_binary(candidates: list[str]) -> str | None:
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


GS_BIN = _find_binary(["gswin64c", "gswin32c", "gs"] if os.name == "nt" else ["gs"])
QPDF_BIN = _find_binary(["qpdf"])
FFMPEG_BIN = _find_binary(["ffmpeg"])
FFPROBE_BIN = _find_binary(["ffprobe"])


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.2f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def build_output_filename(sanitized_name: str) -> str:
    p = Path(sanitized_name)
    return f"{p.stem}_compressed{p.suffix}"


def _sanitize_job(job: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "jobId", "status", "progress", "stage", "originalName", "outputName",
        "format", "category", "originalSize", "compressedSize", "spaceSaved",
        "reductionPercent", "targetSizeBytes", "targetAchieved", "warning",
        "error", "engine", "createdAt", "updatedAt",
    )
    return {k: job.get(k) for k in keys}


def register_uploaded_file(
    *,
    job_id: str,
    file_path: Path,
    original_name: str,
    fmt: str,
    category: str,
    size: int,
) -> dict[str, Any]:
    now = int(time.time() * 1000)
    job = {
        "jobId": job_id,
        "status": "uploaded",
        "progress": 0,
        "stage": "Ready for compression",
        "originalName": original_name,
        "outputName": build_output_filename(original_name),
        "format": fmt,
        "category": category,
        "originalSize": size,
        "compressedSize": None,
        "spaceSaved": None,
        "reductionPercent": None,
        "targetSizeBytes": None,
        "targetAchieved": None,
        "warning": None,
        "error": None,
        "engine": "server",
        "inputPath": str(file_path),
        "outputPath": None,
        "jobDir": str(file_path.parent),
        "createdAt": now,
        "updatedAt": now,
    }
    _JOBS[job_id] = job
    return _sanitize_job(job)


def _update_job(job_id: str, **patch: Any) -> None:
    job = _JOBS.get(job_id)
    if job is not None:
        job.update(patch)
        job["updatedAt"] = int(time.time() * 1000)


def get_job(job_id: str) -> dict[str, Any] | None:
    return _JOBS.get(job_id)


def get_job_status(job_id: str) -> dict[str, Any] | None:
    job = _JOBS.get(job_id)
    return _sanitize_job(job) if job else None


def delete_job(job_id: str) -> bool:
    job = _JOBS.pop(job_id, None)
    if job:
        return cleanup_job_directory(job.get("jobDir") or job_id)
    return cleanup_job_directory(job_id)


def _safe_zip_validate(zf: zipfile.ZipFile) -> None:
    infos = zf.infolist()
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise ValueError(f"Archive contains too many entries ({len(infos)} > {MAX_ARCHIVE_ENTRIES}).")
    total_uncompressed = 0
    for info in infos:
        name = info.filename
        if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
            raise ValueError(f"Unsafe archive entry path detected: {name}")
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Archive exceeds safe uncompressed size limit (possible Zip Bomb).")


def _compress_image_bytes(
    data: bytes,
    fmt: str,
    quality: int = 75,
    max_width: int = 0,
    max_height: int = 0,
    png_quantize: bool = True,
) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        if (max_width and w > max_width) or (max_height and h > max_height):
            img.thumbnail((max_width or w, max_height or h), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        norm = fmt.lower().lstrip(".")
        if norm in ("jpg", "jpeg"):
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(out, format="JPEG", quality=max(10, min(95, int(quality))), optimize=True, progressive=True)
        elif norm == "webp":
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            img.save(out, format="WEBP", quality=max(10, min(95, int(quality))), method=6)
        elif norm == "png":
            if png_quantize and quality < 92:
                colors = max(16, min(256, int(16 + (quality / 92.0) * 240)))
                if img.mode == "RGBA":
                    quantized = img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
                else:
                    quantized = img.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
                quantized.save(out, format="PNG", optimize=True, compress_level=9)
            else:
                img.save(out, format="PNG", optimize=True, compress_level=9)
        else:
            return data
        return out.getvalue()


def _compress_image(
    input_path: Path,
    output_path: Path,
    fmt: str,
    settings: dict[str, Any],
    target_bytes: int | None,
    on_progress: Callable[[int, str], None],
) -> dict[str, Any]:
    quality = max(10, min(95, int(settings.get("quality") or 78)))
    max_width = int(settings.get("maxWidth") or 0)
    max_height = int(settings.get("maxHeight") or 0)
    raw = input_path.read_bytes()
    orig_size = len(raw)

    on_progress(35, f"Compressing {fmt.upper()} image with Pillow")
    best = _compress_image_bytes(raw, fmt, quality=quality, max_width=max_width, max_height=max_height)
    used_q = quality

    if target_bytes and len(best) > target_bytes:
        on_progress(60, "Tuning quality toward target size")
        for q in [q for q in (75, 65, 55, 45, 35, 25, 18, 12) if q < quality] or [12]:
            cand = _compress_image_bytes(raw, fmt, quality=q, max_width=max_width, max_height=max_height)
            if len(cand) < len(best):
                best = cand
                used_q = q
            if len(best) <= target_bytes:
                break

        if len(best) > target_bytes:
            on_progress(80, "Scaling dimensions toward target size")
            with Image.open(io.BytesIO(raw)) as im:
                base_w, base_h = im.size
            for scale in (0.8, 0.65, 0.5, 0.35, 0.25):
                sw = max(64, int((max_width or base_w) * scale))
                sh = max(64, int((max_height or base_h) * scale))
                cand = _compress_image_bytes(raw, fmt, quality=min(used_q, 30), max_width=sw, max_height=sh)
                if len(cand) < len(best):
                    best = cand
                if len(best) <= target_bytes:
                    break

    if len(best) >= orig_size:
        output_path.write_bytes(raw)
        return {"compressedSize": orig_size, "alreadyOptimal": True}

    output_path.write_bytes(best)
    return {"compressedSize": len(best), "alreadyOptimal": False}


def _run_gs_pdf(input_path: Path, output_path: Path, preset: str, dpi: int, jpeg_q: int) -> None:
    if not GS_BIN:
        raise RuntimeError("Ghostscript not installed")
    args = [
        GS_BIN,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        f"-dPDFSETTINGS={preset}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        f"-dColorImageResolution={dpi}",
        f"-dGrayImageResolution={dpi}",
        f"-dMonoImageResolution={max(dpi, 150)}",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        f"-dJPEGQ={jpeg_q}",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]
    subprocess.run(args, check=True, timeout=120, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _compress_pdf_pypdf_fallback(input_path: Path, output_path: Path, quality: int = 60) -> int:
    reader = PdfReader(str(input_path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for page in writer.pages:
        for img in getattr(page, "images", []):
            try:
                img.replace(img.image, quality=quality)
            except Exception:
                pass
        try:
            page.compress_content_streams(level=9)
        except Exception:
            pass
    writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    with output_path.open("wb") as f:
        writer.write(f)
    return output_path.stat().st_size


def _compress_pdf(
    input_path: Path,
    output_path: Path,
    settings: dict[str, Any],
    target_bytes: int | None,
    on_progress: Callable[[int, str], None],
) -> dict[str, Any]:
    orig_size = input_path.stat().st_size
    level = str(settings.get("pdfQuality") or "medium").lower()
    custom_dpi = int(settings.get("imageDpi") or 0)
    presets = {
        "high": ("/printer", custom_dpi or 200, 82),
        "medium": ("/ebook", custom_dpi or 150, 68),
        "low": ("/screen", custom_dpi or 96, 45),
    }
    pdf_preset, dpi, jpeg_q = presets.get(level, presets["medium"])

    if not GS_BIN:
        on_progress(45, "Compressing PDF streams and images with pypdf")
        best_size = _compress_pdf_pypdf_fallback(input_path, output_path, quality=jpeg_q)
        if best_size >= orig_size:
            shutil.copy2(input_path, output_path)
            return {"compressedSize": orig_size, "alreadyOptimal": True}
        return {"compressedSize": best_size, "alreadyOptimal": False}

    temp_gs = output_path.with_suffix(".gs.pdf")
    temp_qpdf = output_path.with_suffix(".qpdf.pdf")
    extra_temps: list[Path] = [temp_gs, temp_qpdf]

    try:
        on_progress(30, "Optimizing PDF streams and images with Ghostscript")
        _run_gs_pdf(input_path, temp_gs, pdf_preset, dpi, jpeg_q)
        best_path = temp_gs
        best_size = temp_gs.stat().st_size

        if QPDF_BIN:
            on_progress(55, "Compressing PDF object streams with QPDF")
            try:
                subprocess.run(
                    [QPDF_BIN, "--object-streams=generate", "--recompress-flate", "--compression-level=9", str(temp_gs), str(temp_qpdf)],
                    check=True,
                    timeout=60,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                q_size = temp_qpdf.stat().st_size
                if 0 < q_size < best_size:
                    best_path = temp_qpdf
                    best_size = q_size
            except Exception:
                pass

        if target_bytes and best_size > target_bytes:
            steps = [("/ebook", 120, 55), ("/screen", 96, 42), ("/screen", 72, 30), ("/screen", 56, 20)]
            for idx, (st_preset, st_dpi, st_q) in enumerate(steps, start=1):
                on_progress(60 + idx * 8, f"Refining PDF pass {idx}/{len(steps)}")
                cand = output_path.with_suffix(f".p{idx}.pdf")
                extra_temps.append(cand)
                try:
                    _run_gs_pdf(input_path, cand, st_preset, st_dpi, st_q)
                    c_size = cand.stat().st_size
                    if 0 < c_size < best_size:
                        best_path = cand
                        best_size = c_size
                    if best_size <= target_bytes:
                        break
                except Exception:
                    pass

        if best_size >= orig_size:
            shutil.copy2(input_path, output_path)
            return {"compressedSize": orig_size, "alreadyOptimal": True}

        shutil.copy2(best_path, output_path)
        return {"compressedSize": output_path.stat().st_size, "alreadyOptimal": False}
    finally:
        for t in extra_temps:
            safe_delete_file(t)


def _compress_video(
    input_path: Path,
    output_path: Path,
    fmt: str,
    settings: dict[str, Any],
    target_bytes: int | None,
    on_progress: Callable[[int, str], None],
) -> dict[str, Any]:
    if not FFMPEG_BIN or not FFPROBE_BIN:
        raise RuntimeError("FFmpeg/FFprobe is required for MP4/MOV compression. Please install FFmpeg and add it to PATH.")

    orig_size = input_path.stat().st_size
    on_progress(20, "Inspecting video streams with FFprobe")
    probe = subprocess.run(
        [FFPROBE_BIN, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(input_path)],
        check=True,
        timeout=30,
        capture_output=True,
        text=True,
    )
    info = json.loads(probe.stdout)
    streams = info.get("streams") or []
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(info.get("format", {}).get("duration") or v_stream.get("duration") or 1.0)
    duration = duration if duration > 0 else 1.0
    orig_h = int(v_stream.get("height") or 720)

    res_map = {"original": 0, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
    max_h = res_map.get(str(settings.get("resolution") or "original").lower(), 0)
    crf = max(18, min(40, int(settings.get("crf") or 28)))
    audio_kbps = 96 if has_audio else 0
    v_kbps = int(settings.get("videoBitrateKbps") or 0)

    if target_bytes:
        total_kbps = (target_bytes * 8 * 0.92) / duration / 1000.0
        if has_audio and total_kbps < 220:
            audio_kbps = 64
        v_kbps = max(80, int(total_kbps - audio_kbps))
        if v_kbps < 350 and (max_h == 0 or max_h > 480):
            max_h = 480

    def encode(out_p: Path, cur_crf: int, cur_v_kbps: int, cur_h: int, cur_a_kbps: int) -> int:
        args = [FFMPEG_BIN, "-y", "-i", str(input_path), "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p"]
        if cur_h > 0:
            args += ["-vf", f"scale=-2:'min({cur_h},ih)'"]
        if cur_v_kbps > 0:
            args += ["-b:v", f"{cur_v_kbps}k", "-maxrate", f"{int(cur_v_kbps * 1.15)}k", "-bufsize", f"{cur_v_kbps * 2}k"]
        else:
            args += ["-crf", str(cur_crf)]
        if has_audio:
            args += ["-c:a", "aac", "-b:a", f"{cur_a_kbps}k"]
        else:
            args += ["-an"]
        args += ["-movflags", "+faststart", "-f", "mov" if fmt == "mov" else "mp4", str(out_p)]
        subprocess.run(args, check=True, timeout=240, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out_p.stat().st_size

    on_progress(45, f"Encoding {fmt.upper()} with FFmpeg (H.264)")
    best_size = encode(output_path, crf, v_kbps, max_h, audio_kbps)

    if target_bytes and best_size > target_bytes:
        on_progress(75, "Refining video bitrate toward target size")
        pass2 = output_path.with_suffix(f".p2.{fmt}")
        try:
            ratio = target_bytes / best_size
            tight_v = max(50, int((v_kbps or 400) * ratio * 0.85))
            tight_h = min(orig_h, 480) if max_h == 0 else min(max_h, 360)
            p2_size = encode(pass2, 34, tight_v, tight_h, 48 if has_audio else 0)
            if 0 < p2_size < best_size:
                pass2.replace(output_path)
                best_size = p2_size
            else:
                safe_delete_file(pass2)
        except Exception:
            safe_delete_file(pass2)

    if best_size >= orig_size:
        shutil.copy2(input_path, output_path)
        return {"compressedSize": orig_size, "alreadyOptimal": True}
    return {"compressedSize": best_size, "alreadyOptimal": False}


def _repack_office(input_path: Path, output_path: Path, img_q: int, max_dim: int) -> int:
    media_exts = {".jpg", ".jpeg", ".png", ".webp"}
    with zipfile.ZipFile(input_path, "r") as zin:
        _safe_zip_validate(zin)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                low = info.filename.lower()
                ext = Path(low).suffix
                is_media = (low.startswith("word/media/") or low.startswith("ppt/media/")) and ext in media_exts
                if is_media and len(data) > 4096:
                    try:
                        opt = _compress_image_bytes(data, ext.lstrip("."), quality=img_q, max_width=max_dim, max_height=max_dim)
                        if len(opt) < len(data):
                            data = opt
                    except Exception:
                        pass
                zinfo = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
                zinfo.external_attr = info.external_attr
                zout.writestr(zinfo, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output_path.stat().st_size


def _compress_office(
    input_path: Path,
    output_path: Path,
    settings: dict[str, Any],
    target_bytes: int | None,
    on_progress: Callable[[int, str], None],
) -> dict[str, Any]:
    orig_size = input_path.stat().st_size
    level = str(settings.get("optimizationLevel") or "balanced").lower()
    preset = {"light": (82, 1920), "balanced": (68, 1440), "aggressive": (48, 1024)}
    q, dim = preset.get(level, (68, 1440))
    if settings.get("imageQuality"):
        q = max(15, min(95, int(settings["imageQuality"])))

    on_progress(45, "Optimizing OpenXML document media and DEFLATE streams")
    best_size = _repack_office(input_path, output_path, q, dim)

    if target_bytes and best_size > target_bytes:
        tmp = output_path.with_suffix(".try")
        for tq, tdim in ((55, 1280), (40, 960), (28, 720), (18, 540)):
            try:
                sz = _repack_office(input_path, tmp, tq, tdim)
                if sz < best_size:
                    tmp.replace(output_path)
                    best_size = sz
                else:
                    safe_delete_file(tmp)
                if best_size <= target_bytes:
                    break
            except Exception:
                safe_delete_file(tmp)

    if best_size >= orig_size:
        shutil.copy2(input_path, output_path)
        return {"compressedSize": orig_size, "alreadyOptimal": True}
    return {"compressedSize": best_size, "alreadyOptimal": False}


def _compress_zip(
    input_path: Path,
    output_path: Path,
    settings: dict[str, Any],
    target_bytes: int | None,
    on_progress: Callable[[int, str], None],
) -> dict[str, Any]:
    orig_size = input_path.stat().st_size
    level = 9 if target_bytes else max(1, min(9, int(settings.get("compressionLevel") or 9)))
    opt_media = bool(settings.get("optimizeEmbeddedMedia", False))
    media_exts = {".jpg", ".jpeg", ".png", ".webp"}

    def pack(out_p: Path, lvl: int, media_q: int = 72) -> int:
        with zipfile.ZipFile(input_path, "r") as zin:
            _safe_zip_validate(zin)
            with zipfile.ZipFile(out_p, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=lvl) as zout:
                for info in zin.infolist():
                    if info.is_dir():
                        zout.writestr(info, b"")
                        continue
                    data = zin.read(info.filename)
                    ext = Path(info.filename).suffix.lower()
                    if opt_media and ext in media_exts and len(data) > 4096:
                        try:
                            opt = _compress_image_bytes(data, ext.lstrip("."), quality=media_q)
                            if len(opt) < len(data):
                                data = opt
                        except Exception:
                            pass
                    zinfo = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
                    zinfo.external_attr = info.external_attr
                    zout.writestr(zinfo, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=lvl)
        return out_p.stat().st_size

    on_progress(45, f"Repacking ZIP archive (DEFLATE level {level})")
    best_size = pack(output_path, level, 72)

    if target_bytes and best_size > target_bytes and opt_media:
        tmp = output_path.with_suffix(".try.zip")
        for mq in (50, 32, 18):
            sz = pack(tmp, 9, mq)
            if sz < best_size:
                tmp.replace(output_path)
                best_size = sz
            else:
                safe_delete_file(tmp)
            if best_size <= target_bytes:
                break

    if best_size >= orig_size:
        shutil.copy2(input_path, output_path)
        return {"compressedSize": orig_size, "alreadyOptimal": True}
    return {"compressedSize": best_size, "alreadyOptimal": False}


def process_compression_job(
    job_id: str,
    *,
    target_size_bytes: int | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    job = _JOBS.get(job_id)
    if not job:
        raise ValueError("Compression job not found or expired.")
    input_path = Path(job["inputPath"])
    if not input_path.is_file():
        raise ValueError("Uploaded source file is no longer available.")

    parsed_target = int(target_size_bytes) if target_size_bytes and int(target_size_bytes) > 0 else None
    if parsed_target is not None and parsed_target >= job["originalSize"]:
        raise ValueError("Target size must be smaller than the original file size.")

    output_path = Path(job["jobDir"]) / job["outputName"]
    _update_job(
        job_id,
        status="processing",
        progress=10,
        stage=f'Initializing {job["format"].upper()} compression',
        targetSizeBytes=parsed_target,
        outputPath=str(output_path),
        warning=None,
        error=None,
    )

    on_progress = lambda pct, stage: _update_job(job_id, progress=pct, stage=stage)
    cfg = settings or {}
    fmt = job["format"]

    try:
        if fmt in ("jpg", "jpeg", "png", "webp"):
            res = _compress_image(input_path, output_path, fmt, cfg, parsed_target, on_progress)
        elif fmt == "pdf":
            res = _compress_pdf(input_path, output_path, cfg, parsed_target, on_progress)
        elif fmt in ("mp4", "mov"):
            res = _compress_video(input_path, output_path, fmt, cfg, parsed_target, on_progress)
        elif fmt in ("docx", "pptx"):
            res = _compress_office(input_path, output_path, cfg, parsed_target, on_progress)
        elif fmt == "zip":
            res = _compress_zip(input_path, output_path, cfg, parsed_target, on_progress)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        compressed_size = output_path.stat().st_size
        orig_size = job["originalSize"]
        space_saved = max(0, orig_size - compressed_size)
        reduction_pct = round((space_saved / orig_size) * 100.0, 2) if orig_size > 0 else 0.0

        target_achieved = None
        warning = None
        if parsed_target is not None:
            target_achieved = compressed_size <= parsed_target
            if not target_achieved:
                warning = (
                    f"Target size of {format_bytes(parsed_target)} could not be reached without corrupting the file. "
                    f"Compressed as much as possible to {format_bytes(compressed_size)} ({reduction_pct}% reduction)."
                )

        if res.get("alreadyOptimal"):
            note = "This file is already highly compressed; original bytes were preserved intact."
            warning = f"{warning} {note}" if warning else note

        _update_job(
            job_id,
            status="completed",
            progress=100,
            stage="Compression complete",
            compressedSize=compressed_size,
            spaceSaved=space_saved,
            reductionPercent=reduction_pct,
            targetAchieved=target_achieved,
            warning=warning,
        )
        return _sanitize_job(_JOBS[job_id])
    except Exception as exc:
        _update_job(job_id, status="failed", progress=0, stage="Compression failed", error=str(exc))
        raise
