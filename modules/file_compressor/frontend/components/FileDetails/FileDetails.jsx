(function () {
  const { FORMAT_META, formatBytes } = window.UFC;

  window.UFC.FileDetails = function FileDetails({ file, format, plannedEngine, disabled, onRemove }) {
    const meta = FORMAT_META[format];

    return (
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
        <div className="flex items-center gap-4 min-w-0">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl font-bold text-xs ${meta.badgeColor}`}>
            {format.toUpperCase()}
          </div>

          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-slate-900 dark:text-slate-100">
              {file.name}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span className={`rounded px-2 py-0.5 font-semibold ${meta.badgeColor}`}>
                {meta.label}
              </span>
              <span>&bull;</span>
              <span className="font-medium text-slate-700 dark:text-slate-300">
                Original: {formatBytes(file.size)}
              </span>
              <span>&bull;</span>
              <span className="inline-flex items-center gap-1 rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-slate-700 dark:text-slate-300">
                {plannedEngine === 'browser' ? 'Browser Engine' : 'Server Engine'}
              </span>
            </div>
          </div>
        </div>

        <button
          type="button"
          disabled={disabled}
          onClick={onRemove}
          className="inline-flex items-center justify-center gap-1.5 self-end sm:self-center rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
        >
          Change file
        </button>
      </div>
    );
  };
})();
