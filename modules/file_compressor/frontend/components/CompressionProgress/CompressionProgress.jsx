(function () {
  window.UFC.CompressionProgress = function CompressionProgress({ state }) {
    if (!state.active) return null;
    const pct = Math.max(0, Math.min(100, Math.round(state.progress)));

    return (
      <div className="rounded-2xl border border-blue-200 dark:border-blue-900/60 bg-blue-50/70 dark:bg-blue-950/30 p-5 space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
              {state.stage || 'Compressing file...'}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {state.engine === 'browser'
                ? 'Running locally in your browser'
                : 'Processing on local compression server'}
            </p>
          </div>
          <span className="text-sm font-bold tabular-nums text-blue-700 dark:text-blue-300">
            {pct}%
          </span>
        </div>

        <div className="h-2.5 w-full overflow-hidden rounded-full bg-blue-200/70 dark:bg-slate-800">
          <div
            className="h-full rounded-full bg-blue-600 dark:bg-blue-500 transition-all duration-300 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    );
  };
})();
