(function () {
  const { formatBytes } = window.UFC;

  window.UFC.CompressionResults = function CompressionResults({ result, onReset }) {
    const retainedRatio =
      result.originalSize > 0
        ? Math.min(100, Math.max(4, Math.round((result.compressedSize / result.originalSize) * 100)))
        : 100;

    const targetMissed = result.targetAchieved === false;

    const handleDownload = () => {
      const link = document.createElement('a');
      link.href = result.downloadUrl;
      link.download = result.outputName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };

    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              {targetMissed
                ? 'Compressed (Target Size Not Fully Reached)'
                : result.targetAchieved === true
                ? 'Compression Complete — Target Size Achieved'
                : 'Compression Complete'}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {result.engine === 'browser'
                ? 'Processed locally in browser'
                : 'Processed on server (temporary files auto-expire)'}
            </p>
          </div>

          <span
            className={`rounded-full px-3 py-1 text-xs font-bold ${
              result.reductionPercent > 0
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
            }`}
          >
            -{result.reductionPercent}% size
          </span>
        </div>

        {result.warning && (
          <div
            role="status"
            className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200"
          >
            &#9888; {result.warning}
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800 p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Original Size</p>
            <p className="mt-1 text-lg font-bold tabular-nums">{formatBytes(result.originalSize)}</p>
          </div>
          <div className="rounded-xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200/80 dark:border-blue-900/60 p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-blue-600 dark:text-blue-400">Compressed Size</p>
            <p className="mt-1 text-lg font-bold text-blue-700 dark:text-blue-300 tabular-nums">
              {formatBytes(result.compressedSize)}
            </p>
          </div>
          <div className="rounded-xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-900/60 p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-emerald-700 dark:text-emerald-400">Space Saved</p>
            <p className="mt-1 text-lg font-bold text-emerald-700 dark:text-emerald-300 tabular-nums">
              {formatBytes(result.spaceSaved)}
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800 p-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Reduction</p>
            <p className="mt-1 text-lg font-bold tabular-nums">{result.reductionPercent}%</p>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>
              {formatBytes(result.originalSize)} &rarr;{' '}
              <strong className="text-slate-900 dark:text-slate-100">{formatBytes(result.compressedSize)}</strong>
            </span>
            {result.targetSizeBytes && (
              <span>
                Target: {formatBytes(result.targetSizeBytes)} ({result.targetAchieved ? 'Met' : 'Not met'})
              </span>
            )}
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500 transition-all duration-500"
              style={{ width: `${retainedRatio}%` }}
            />
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pt-1">
          <button
            type="button"
            onClick={handleDownload}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-700 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors"
          >
            Download {result.outputName}
          </button>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            Compress Another File
          </button>
        </div>
      </div>
    );
  };
})();
