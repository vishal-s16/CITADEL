window.UFC = window.UFC || {};

window.UFC.FORMAT_META = {
  pdf: {
    label: 'PDF',
    category: 'pdf',
    extensions: ['.pdf'],
    defaultEngine: 'server',
    maxSizeMB: 100,
    badgeColor: 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300',
  },
  jpg: {
    label: 'JPG / JPEG',
    category: 'image',
    extensions: ['.jpg', '.jpeg'],
    defaultEngine: 'browser',
    maxSizeMB: 50,
    badgeColor: 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300',
  },
  png: {
    label: 'PNG',
    category: 'image',
    extensions: ['.png'],
    defaultEngine: 'browser',
    maxSizeMB: 50,
    badgeColor: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
  },
  webp: {
    label: 'WEBP',
    category: 'image',
    extensions: ['.webp'],
    defaultEngine: 'browser',
    maxSizeMB: 50,
    badgeColor: 'bg-teal-100 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300',
  },
  mp4: {
    label: 'MP4',
    category: 'video',
    extensions: ['.mp4'],
    defaultEngine: 'server',
    maxSizeMB: 200,
    badgeColor: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300',
  },
  mov: {
    label: 'MOV',
    category: 'video',
    extensions: ['.mov'],
    defaultEngine: 'server',
    maxSizeMB: 200,
    badgeColor: 'bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300',
  },
  docx: {
    label: 'DOCX',
    category: 'document',
    extensions: ['.docx'],
    defaultEngine: 'server',
    maxSizeMB: 100,
    badgeColor: 'bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300',
  },
  pptx: {
    label: 'PPTX',
    category: 'document',
    extensions: ['.pptx'],
    defaultEngine: 'server',
    maxSizeMB: 100,
    badgeColor: 'bg-orange-100 text-orange-700 dark:bg-orange-950/60 dark:text-orange-300',
  },
  zip: {
    label: 'ZIP',
    category: 'archive',
    extensions: ['.zip'],
    defaultEngine: 'browser',
    maxSizeMB: 200,
    badgeColor: 'bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200',
  },
};

window.UFC.ACCEPT_STRING = '.pdf,.jpg,.jpeg,.png,.webp,.mp4,.mov,.docx,.pptx,.zip';

window.UFC.DEFAULT_SETTINGS = {
  quality: 78,
  maxWidth: 0,
  maxHeight: 0,
  pdfQuality: 'medium',
  imageDpi: 150,
  resolution: 'original',
  crf: 28,
  videoBitrateKbps: 0,
  optimizationLevel: 'balanced',
  imageQuality: 68,
  compressionLevel: 9,
  optimizeEmbeddedMedia: false,
  preferBrowserEngine: true,
};

window.UFC.detectFormatFromFile = function detectFormatFromFile(file) {
  const lower = (file.name || '').toLowerCase();
  if (lower.endsWith('.pdf')) return 'pdf';
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'jpg';
  if (lower.endsWith('.png')) return 'png';
  if (lower.endsWith('.webp')) return 'webp';
  if (lower.endsWith('.mp4')) return 'mp4';
  if (lower.endsWith('.mov')) return 'mov';
  if (lower.endsWith('.docx')) return 'docx';
  if (lower.endsWith('.pptx')) return 'pptx';
  if (lower.endsWith('.zip')) return 'zip';
  return null;
};

window.UFC.formatBytes = function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

window.UFC.buildCompressedFilename = function buildCompressedFilename(originalName) {
  const dotIdx = originalName.lastIndexOf('.');
  if (dotIdx <= 0) return `${originalName}_compressed`;
  return `${originalName.slice(0, dotIdx)}_compressed${originalName.slice(dotIdx)}`;
};
