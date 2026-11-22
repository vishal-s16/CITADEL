(function () {
  const { useEffect, useMemo, useState } = React;
  const {
    DEFAULT_SETTINGS,
    canCompressInBrowser,
    compressInBrowser,
    compressOnServer,
    cleanupServerJob,
    FileUploader,
    FileDetails,
    TargetSizeInput,
    CompressionSettings,
    CompressionProgress,
    CompressionResults,
    FilePreview,
  } = window.UFC;

  function App() {
    const [darkMode, setDarkMode] = useState(() =>
      window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)').matches : false
    );
    const [selectedFile, setSelectedFile] = useState(null);
    const [fileFormat, setFileFormat] = useState(null);
    const [targetValue, setTargetValue] = useState('');
    const [targetUnit, setTargetUnit] = useState('KB');
    const [settings, setSettings] = useState(DEFAULT_SETTINGS);
    const [progress, setProgress] = useState({ active: false, progress: 0, stage: '', engine: 'browser' });
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
      document.documentElement.classList.toggle('dark', darkMode);
    }, [darkMode]);

    useEffect(() => {
      return () => {
        if (result && result.engine === 'browser' && result.downloadUrl.startsWith('blob:')) {
          URL.revokeObjectURL(result.downloadUrl);
        }
      };
    }, [result]);

    const plannedEngine = useMemo(() => {
      if (!selectedFile || !fileFormat) return 'server';
      return canCompressInBrowser(fileFormat, selectedFile.size, settings) ? 'browser' : 'server';
    }, [selectedFile, fileFormat, settings]);

    const { targetBytes, targetError } = useMemo(() => {
      if (!targetValue.trim() || !selectedFile) return { targetBytes: null, targetError: null };
      const num = Number(targetValue);
      if (!Number.isFinite(num) || num <= 0) {
        return { targetBytes: null, targetError: 'Target size must be greater than 0.' };
      }
      const bytes = Math.floor(num * (targetUnit === 'MB' ? 1024 * 1024 : 1024));
      if (bytes >= selectedFile.size) {
        return { targetBytes: null, targetError: 'Target size must be smaller than the original file size.' };
      }
      if (bytes < 512) {
        return { targetBytes: null, targetError: 'Target size is too small (minimum 0.5 KB).' };
      }
      return { targetBytes: bytes, targetError: null };
    }, [targetValue, targetUnit, selectedFile]);

    const cleanupActiveResult = async () => {
      if (result && result.jobId) {
        await cleanupServerJob(result.jobId).catch(() => {});
      }
      if (result && result.engine === 'browser' && result.downloadUrl.startsWith('blob:')) {
        URL.revokeObjectURL(result.downloadUrl);
      }
    };

    const handleFileSelected = async (file, format) => {
      await cleanupActiveResult();
      setSelectedFile(file);
      setFileFormat(format);
      setResult(null);
      setError(null);
      setTargetValue('');
      setTargetUnit(file.size >= 2 * 1024 * 1024 ? 'MB' : 'KB');
    };

    const handleReset = async () => {
      await cleanupActiveResult();
      setSelectedFile(null);
      setFileFormat(null);
      setResult(null);
      setError(null);
      setTargetValue('');
      setProgress({ active: false, progress: 0, stage: '', engine: 'browser' });
    };

    const handleCompress = async () => {
      if (!selectedFile || !fileFormat || targetError) return;
      await cleanupActiveResult();
      setResult(null);
      setError(null);

      const engine = plannedEngine;
      setProgress({ active: true, progress: 5, stage: 'Preparing file...', engine });

      try {
        let output;
        if (engine === 'browser') {
          output = await compressInBrowser(selectedFile, fileFormat, targetBytes, settings, (pct, stage) =>
            setProgress({ active: true, progress: pct, stage, engine: 'browser' })
          );
        } else {
          output = await compressOnServer(selectedFile, targetBytes, settings, (pct, stage) =>
            setProgress({ active: true, progress: pct, stage, engine: 'server' })
          );
        }
        setResult(output);
      } catch (err) {
        setError(err && err.message ? err.message : 'Compression failed.');
      } finally {
        setProgress((prev) => ({ ...prev, active: false }));
      }
    };

    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 dark:border-slate-800/80 bg-white/85 dark:bg-slate-950/85 backdrop-blur">
          <div className="mx-auto flex max-w-4xl items-center justify-between px-4 sm:px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white font-bold text-sm shadow-sm">
                UFC
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight">Universal File Compressor</h1>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Zero-npm hybrid browser &amp; server compression for 9 formats
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setDarkMode((d) => !d)}
              className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100/70 dark:bg-slate-900 px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-slate-800 transition-colors"
            >
              {darkMode ? 'Light Mode' : 'Dark Mode'}
            </button>
          </div>
        </header>

        <main className="mx-auto max-w-4xl px-4 sm:px-6 py-8 space-y-6">
          {!selectedFile || !fileFormat ? (
            <FileUploader disabled={progress.active} onFileSelected={handleFileSelected} />
          ) : (
            <>
              <FileDetails
                file={selectedFile}
                format={fileFormat}
                plannedEngine={plannedEngine}
                disabled={progress.active}
                onRemove={handleReset}
              />

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <TargetSizeInput
                  originalSize={selectedFile.size}
                  value={targetValue}
                  unit={targetUnit}
                  disabled={progress.active}
                  onValueChange={setTargetValue}
                  onUnitChange={setTargetUnit}
                  validationError={targetError}
                />

                <CompressionSettings
                  format={fileFormat}
                  settings={settings}
                  disabled={progress.active}
                  onChange={(patch) => setSettings((prev) => ({ ...prev, ...patch }))}
                />
              </div>

              {!progress.active && (
                <button
                  type="button"
                  disabled={Boolean(targetError)}
                  onClick={handleCompress}
                  className="w-full rounded-2xl bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 disabled:text-slate-500 px-6 py-4 text-base font-semibold text-white shadow-sm transition-colors"
                >
                  {result ? 'Re-compress with Updated Settings' : 'Compress File'}
                </button>
              )}
            </>
          )}

          <CompressionProgress state={progress} />

          {error && (
            <div
              role="alert"
              className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300"
            >
              <p className="font-semibold">Compression Error</p>
              <p className="mt-0.5">{error}</p>
            </div>
          )}

          {result && selectedFile && (
            <div className="space-y-6">
              <CompressionResults result={result} onReset={handleReset} />
              <FilePreview originalFile={selectedFile} result={result} />
            </div>
          )}
        </main>

        <footer className="mx-auto max-w-4xl px-4 sm:px-6 pb-10 pt-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 dark:border-slate-800 pt-5 text-xs text-slate-500 dark:text-slate-400">
            <span>Files are never stored permanently; temporary files are automatically deleted.</span>
            <span>PDF &bull; JPG &bull; PNG &bull; WEBP &bull; MP4 &bull; MOV &bull; DOCX &bull; PPTX &bull; ZIP</span>
          </div>
        </footer>
      </div>
    );
  }

  ReactDOM.createRoot(document.getElementById('root')).render(<App />);
})();
