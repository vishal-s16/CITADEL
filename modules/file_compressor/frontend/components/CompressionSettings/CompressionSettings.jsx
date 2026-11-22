(function () {
  const { FORMAT_META } = window.UFC;

  window.UFC.CompressionSettings = function CompressionSettings({ format, settings, disabled, onChange }) {
    const category = FORMAT_META[format].category;

    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          {FORMAT_META[format].label} Compression Settings
        </h3>

        {category === 'image' && (
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs font-medium mb-1.5">
                <span className="text-slate-600 dark:text-slate-300">Quality</span>
                <span className="text-blue-600 dark:text-blue-400 font-semibold">{settings.quality}%</span>
              </div>
              <input
                type="range"
                min={15}
                max={95}
                disabled={disabled}
                value={settings.quality}
                onChange={(e) => onChange({ quality: Number(e.target.value) })}
                className="w-full accent-blue-600"
              />
              <div className="flex justify-between text-[11px] text-slate-400 mt-0.5">
                <span>Smaller file</span>
                <span>Higher quality</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                  Max Width (px, optional)
                </label>
                <input
                  type="number"
                  min={0}
                  placeholder="Original"
                  disabled={disabled}
                  value={settings.maxWidth || ''}
                  onChange={(e) => onChange({ maxWidth: Math.max(0, Number(e.target.value) || 0) })}
                  className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                  Max Height (px, optional)
                </label>
                <input
                  type="number"
                  min={0}
                  placeholder="Original"
                  disabled={disabled}
                  value={settings.maxHeight || ''}
                  onChange={(e) => onChange({ maxHeight: Math.max(0, Number(e.target.value) || 0) })}
                  className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
                />
              </div>
            </div>
          </div>
        )}

        {category === 'pdf' && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'high', label: 'High Quality', desc: '200 DPI' },
                { id: 'medium', label: 'Balanced', desc: '150 DPI' },
                { id: 'low', label: 'Max Compress', desc: '96 DPI' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  disabled={disabled}
                  onClick={() =>
                    onChange({
                      pdfQuality: opt.id,
                      imageDpi: opt.id === 'high' ? 200 : opt.id === 'medium' ? 150 : 96,
                    })
                  }
                  className={`rounded-xl border p-2.5 text-left transition-colors ${
                    settings.pdfQuality === opt.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300'
                      : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60'
                  }`}
                >
                  <div className="text-xs font-semibold">{opt.label}</div>
                  <div className="text-[11px] opacity-75">{opt.desc}</div>
                </button>
              ))}
            </div>

            <div>
              <div className="flex justify-between text-xs font-medium mb-1.5">
                <span className="text-slate-600 dark:text-slate-300">Embedded Image DPI</span>
                <span className="text-blue-600 dark:text-blue-400 font-semibold">{settings.imageDpi} DPI</span>
              </div>
              <input
                type="range"
                min={72}
                max={300}
                step={12}
                disabled={disabled}
                value={settings.imageDpi}
                onChange={(e) => onChange({ imageDpi: Number(e.target.value) })}
                className="w-full accent-blue-600"
              />
            </div>
          </div>
        )}

        {category === 'video' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                  Output Resolution
                </label>
                <select
                  disabled={disabled}
                  value={settings.resolution}
                  onChange={(e) => onChange({ resolution: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
                >
                  <option value="original">Keep Original</option>
                  <option value="1080p">1080p (Full HD)</option>
                  <option value="720p">720p (HD)</option>
                  <option value="480p">480p (SD)</option>
                  <option value="360p">360p (Compact)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                  Max Bitrate (kbps, optional)
                </label>
                <input
                  type="number"
                  min={0}
                  step={100}
                  placeholder="Auto (CRF)"
                  disabled={disabled}
                  value={settings.videoBitrateKbps || ''}
                  onChange={(e) => onChange({ videoBitrateKbps: Math.max(0, Number(e.target.value) || 0) })}
                  className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-medium mb-1.5">
                <span className="text-slate-600 dark:text-slate-300">Compression Factor (CRF)</span>
                <span className="text-blue-600 dark:text-blue-400 font-semibold">CRF {settings.crf}</span>
              </div>
              <input
                type="range"
                min={20}
                max={38}
                disabled={disabled}
                value={settings.crf}
                onChange={(e) => onChange({ crf: Number(e.target.value) })}
                className="w-full accent-blue-600"
              />
            </div>
          </div>
        )}

        {category === 'document' && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'light', label: 'Light', desc: 'Preserve detail' },
                { id: 'balanced', label: 'Balanced', desc: 'Recommended' },
                { id: 'aggressive', label: 'Aggressive', desc: 'Max savings' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  disabled={disabled}
                  onClick={() =>
                    onChange({
                      optimizationLevel: opt.id,
                      imageQuality: opt.id === 'light' ? 82 : opt.id === 'balanced' ? 68 : 48,
                    })
                  }
                  className={`rounded-xl border p-2.5 text-left transition-colors ${
                    settings.optimizationLevel === opt.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300'
                      : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60'
                  }`}
                >
                  <div className="text-xs font-semibold">{opt.label}</div>
                  <div className="text-[11px] opacity-75">{opt.desc}</div>
                </button>
              ))}
            </div>

            <div>
              <div className="flex justify-between text-xs font-medium mb-1.5">
                <span className="text-slate-600 dark:text-slate-300">Embedded Media Quality</span>
                <span className="text-blue-600 dark:text-blue-400 font-semibold">{settings.imageQuality}%</span>
              </div>
              <input
                type="range"
                min={25}
                max={90}
                disabled={disabled}
                value={settings.imageQuality}
                onChange={(e) => onChange({ imageQuality: Number(e.target.value) })}
                className="w-full accent-blue-600"
              />
            </div>
          </div>
        )}

        {category === 'archive' && (
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs font-medium mb-1.5">
                <span className="text-slate-600 dark:text-slate-300">DEFLATE Compression Level</span>
                <span className="text-blue-600 dark:text-blue-400 font-semibold">Level {settings.compressionLevel}</span>
              </div>
              <input
                type="range"
                min={1}
                max={9}
                disabled={disabled}
                value={settings.compressionLevel}
                onChange={(e) => onChange({ compressionLevel: Number(e.target.value) })}
                className="w-full accent-blue-600"
              />
            </div>

            <label className="flex items-center gap-2.5 text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                disabled={disabled}
                checked={settings.optimizeEmbeddedMedia}
                onChange={(e) => onChange({ optimizeEmbeddedMedia: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-blue-600"
              />
              <span>Also optimize JPG/PNG/WEBP images inside the ZIP archive (server engine)</span>
            </label>
          </div>
        )}

        {(format === 'jpg' || format === 'webp' || format === 'zip') && (
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
            <label className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400 cursor-pointer">
              <span>Prefer fast browser-side processing when available</span>
              <input
                type="checkbox"
                disabled={disabled}
                checked={settings.preferBrowserEngine}
                onChange={(e) => onChange({ preferBrowserEngine: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-blue-600"
              />
            </label>
          </div>
        )}
      </div>
    );
  };
})();
