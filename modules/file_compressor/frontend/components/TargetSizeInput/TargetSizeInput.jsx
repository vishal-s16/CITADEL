(function () {
  const { formatBytes } = window.UFC;

  window.UFC.TargetSizeInput = function TargetSizeInput({
    originalSize,
    value,
    unit,
    disabled,
    onValueChange,
    onUnitChange,
    validationError,
  }) {
    const applyPreset = (ratio) => {
      const bytes = Math.max(1024, Math.floor(originalSize * ratio));
      if (bytes >= 1024 * 1024) {
        onUnitChange('MB');
        onValueChange((bytes / (1024 * 1024)).toFixed(2));
      } else {
        onUnitChange('KB');
        onValueChange(Math.max(1, Math.round(bytes / 1024)).toString());
      }
    };

    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Target File Size <span className="font-normal text-slate-400">(Optional)</span>
          </h3>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Max &lt; {formatBytes(originalSize)}
          </span>
        </div>

        <div className="flex gap-2">
          <input
            type="number"
            min="0.01"
            step="any"
            disabled={disabled}
            value={value}
            onChange={(e) => onValueChange(e.target.value)}
            placeholder="e.g. 500"
            className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
          />

          <div className="flex rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-950 p-1">
            {['KB', 'MB'].map((u) => (
              <button
                key={u}
                type="button"
                disabled={disabled}
                onClick={() => onUnitChange(u)}
                className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                  unit === u
                    ? 'bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {u}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500 dark:text-slate-400">Quick targets:</span>
          {[
            { label: '75%', ratio: 0.75 },
            { label: '50%', ratio: 0.5 },
            { label: '25%', ratio: 0.25 },
          ].map((preset) => (
            <button
              key={preset.label}
              type="button"
              disabled={disabled}
              onClick={() => applyPreset(preset.ratio)}
              className="rounded-lg border border-slate-200 dark:border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
            >
              {preset.label} of original
            </button>
          ))}
          {value && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => onValueChange('')}
              className="ml-auto text-xs font-medium text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
              Clear
            </button>
          )}
        </div>

        {validationError && (
          <p className="text-xs font-medium text-amber-600 dark:text-amber-400">
            &#9888; {validationError}
          </p>
        )}
      </div>
    );
  };
})();
