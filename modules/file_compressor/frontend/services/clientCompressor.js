window.UFC = window.UFC || {};

(function () {
  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error('Failed to decode image in browser. The file may be corrupted.'));
      };
      img.src = url;
    });
  }

  function canvasToBlob(canvas, mimeType, quality) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (!blob) return reject(new Error('Browser image encoding failed.'));
          resolve(blob);
        },
        mimeType,
        quality
      );
    });
  }

  function renderToCanvas(img, maxWidth, maxHeight, fillWhiteBg) {
    let width = img.naturalWidth;
    let height = img.naturalHeight;

    if (maxWidth > 0 && width > maxWidth) {
      height = Math.max(1, Math.round((height * maxWidth) / width));
      width = maxWidth;
    }
    if (maxHeight > 0 && height > maxHeight) {
      width = Math.max(1, Math.round((width * maxHeight) / height));
      height = maxHeight;
    }

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas 2D context is unavailable.');

    if (fillWhiteBg) {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, width, height);
    }
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, width, height);
    return canvas;
  }

  function finalizeBrowserResult({ file, finalBlob, format, outputName, targetSizeBytes, alreadyOptimal }) {
    const { FORMAT_META, formatBytes } = window.UFC;
    const originalSize = file.size;
    const compressedSize = finalBlob.size;
    const spaceSaved = Math.max(0, originalSize - compressedSize);
    const reductionPercent =
      originalSize > 0 ? Number(((spaceSaved / originalSize) * 100).toFixed(2)) : 0;

    let targetAchieved = null;
    let warning = null;

    if (targetSizeBytes !== null) {
      targetAchieved = compressedSize <= targetSizeBytes;
      if (!targetAchieved) {
        warning = `Requested target size of ${formatBytes(targetSizeBytes)} could not be reached in browser without degrading integrity. Compressed to ${formatBytes(compressedSize)} (${reductionPercent}% reduction).`;
      }
    }

    if (alreadyOptimal) {
      const note = 'File is already highly compressed; original bytes were preserved so the file did not grow larger.';
      warning = warning ? `${warning} ${note}` : note;
    }

    return {
      originalName: file.name,
      outputName,
      format,
      category: FORMAT_META[format].category,
      originalSize,
      compressedSize,
      spaceSaved,
      reductionPercent,
      targetSizeBytes,
      targetAchieved,
      warning,
      engine: 'browser',
      downloadUrl: URL.createObjectURL(finalBlob),
      blob: finalBlob,
      status: 'completed',
    };
  }

  window.UFC.canCompressInBrowser = function canCompressInBrowser(format, fileSize, settings) {
    if (!settings.preferBrowserEngine) return false;
    const MAX_BROWSER_BYTES = 25 * 1024 * 1024;
    if (fileSize > MAX_BROWSER_BYTES) return false;
    if (format === 'jpg' || format === 'webp') return true;
    if (format === 'zip' && !settings.optimizeEmbeddedMedia && typeof window.JSZip !== 'undefined') return true;
    if (format === 'png' && (settings.maxWidth > 0 || settings.maxHeight > 0)) return true;
    return false;
  };

  window.UFC.compressInBrowser = async function compressInBrowser(
    file,
    format,
    targetSizeBytes,
    settings,
    onProgress
  ) {
    const originalSize = file.size;
    const outputName = window.UFC.buildCompressedFilename(file.name);

    if (format === 'zip') {
      onProgress(20, 'Reading ZIP archive in browser');
      const zip = await window.JSZip.loadAsync(file);
      onProgress(55, `Recompressing ZIP (level ${settings.compressionLevel})`);
      const compressedBlob = await zip.generateAsync(
        {
          type: 'blob',
          compression: 'DEFLATE',
          compressionOptions: { level: Math.max(1, Math.min(9, settings.compressionLevel)) },
        },
        (meta) => {
          onProgress(Math.min(95, Math.round(55 + meta.percent * 0.4)), 'Packing ZIP archive');
        }
      );

      const alreadyOptimal = compressedBlob.size >= originalSize;
      return finalizeBrowserResult({
        file,
        finalBlob: alreadyOptimal ? file : compressedBlob,
        format,
        outputName,
        targetSizeBytes,
        alreadyOptimal,
      });
    }

    onProgress(20, 'Decoding image in browser');
    const img = await loadImage(file);
    const mimeMap = { jpg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };
    const mimeType = mimeMap[format];
    const fillWhite = format === 'jpg';
    const maxW = settings.maxWidth || 0;
    const maxH = settings.maxHeight || 0;
    const initQuality = Math.max(0.1, Math.min(0.95, settings.quality / 100));

    onProgress(45, 'Encoding optimized image');
    const initialCanvas = renderToCanvas(img, maxW, maxH, fillWhite);
    let bestBlob = await canvasToBlob(initialCanvas, mimeType, initQuality);

    if (targetSizeBytes && bestBlob.size > targetSizeBytes) {
      if (format === 'jpg' || format === 'webp') {
        onProgress(65, 'Tuning quality toward target size');
        for (const q of [0.7, 0.58, 0.46, 0.34, 0.24, 0.15]) {
          if (q >= initQuality) continue;
          const cand = await canvasToBlob(initialCanvas, mimeType, q);
          if (cand.size < bestBlob.size) bestBlob = cand;
          if (bestBlob.size <= targetSizeBytes) break;
        }
      }

      if (bestBlob.size > targetSizeBytes) {
        onProgress(80, 'Scaling dimensions to approach target size');
        const baseW = maxW || img.naturalWidth;
        const baseH = maxH || img.naturalHeight;
        for (const scale of [0.8, 0.65, 0.5, 0.35, 0.25]) {
          const scaledCanvas = renderToCanvas(
            img,
            Math.max(64, Math.round(baseW * scale)),
            Math.max(64, Math.round(baseH * scale)),
            fillWhite
          );
          const cand = await canvasToBlob(scaledCanvas, mimeType, 0.25);
          if (cand.size < bestBlob.size) bestBlob = cand;
          if (bestBlob.size <= targetSizeBytes) break;
        }
      }
    }

    onProgress(100, 'Compression complete');
    const alreadyOptimal = bestBlob.size >= originalSize;
    return finalizeBrowserResult({
      file,
      finalBlob: alreadyOptimal ? file : bestBlob,
      format,
      outputName,
      targetSizeBytes,
      alreadyOptimal,
    });
  };
})();
