(function () {
  const { useRef, useState } = React;
  const { ACCEPT_STRING, FORMAT_META, detectFormatFromFile } = window.UFC;
  const SUPPORTED_BADGES = ['pdf', 'jpg', 'png', 'webp', 'mp4', 'mov', 'docx', 'pptx', 'zip'];

  window.UFC.FileUploader = function FileUploader({ disabled, onFileSelected }) {
    const inputRef = useRef(null);
    const [isDragging, setIsDragging] = useState(false);
    const [error, setError] = useState(null);

    const validateAndSelect = (files) => {
      setError(null);
      if (!files || files.length === 0) return;

      if (files.length > 1) {
        setError('Only one file can be processed at a time. Please drop or select a single file.');
        return;
      }

      const file = files[0];
      if (file.size === 0) {
        setError('The selected file is empty (0 bytes).');
        return;
      }

      const format = detectFormatFromFile(file);
      if (!format) {
        setError(
          `Unsupported file format for "${file.name}". Supported formats: PDF, JPG/JPEG, PNG, WEBP, MP4, MOV, DOCX, PPTX, ZIP.`
        );
        return;
      }

      const maxBytes = FORMAT_META[format].maxSizeMB * 1024 * 1024;
      if (file.size > maxBytes) {
        setError(`${FORMAT_META[format].label} files must be ${FORMAT_META[format].maxSizeMB} MB or smaller.`);
        return;
      }

      onFileSelected(file, format);
    };

    return (
      <div className="space-y-4">
        <div
          role="button"
          tabIndex={disabled ? -1 : 0}
          onClick={() => !disabled && inputRef.current && inputRef.current.click()}
          onKeyDown={(e) => {
            if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault();
              inputRef.current && inputRef.current.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setIsDragging(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setIsDragging(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (!disabled) validateAndSelect(e.dataTransfer.files);
          }}
          className={`group relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-200 cursor-pointer ${
            isDragging
              ? 'border-blue-500 bg-blue-50/70 dark:bg-blue-950/30 scale-[1.01]'
              : 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-slate-50/80 dark:hover:bg-slate-800/50'
          } ${disabled ? 'opacity-60 pointer-events-none' : ''}`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT_STRING}
            multiple={false}
            className="hidden"
            onChange={(e) => {
              validateAndSelect(e.target.files);
              e.target.value = '';
            }}
          />

          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-blue-600 dark:bg-blue-950/70 dark:text-blue-400 group-hover:scale-105 transition-transform">
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>

          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Drop your file here, or{' '}
            <span className="text-blue-600 dark:text-blue-400 underline underline-offset-4">browse</span>
          </h2>
          <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
            One file at a time &bull; Automatic format detection &bull; Original file is never modified
          </p>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            {SUPPORTED_BADGES.map((fmt) => (
              <span
                key={fmt}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold tracking-wide ${FORMAT_META[fmt].badgeColor}`}
              >
                {FORMAT_META[fmt].label}
              </span>
            ))}
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300"
          >
            <span className="font-bold">!</span>
            <span>{error}</span>
          </div>
        )}
      </div>
    );
  };
})();
