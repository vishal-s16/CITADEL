(function () {
  const { useEffect, useState } = React;

  window.UFC.FilePreview = function FilePreview({ originalFile, result }) {
    const [originalUrl, setOriginalUrl] = useState(null);

    useEffect(() => {
      if (result.category === 'image' || result.category === 'video' || result.category === 'pdf') {
        const url = URL.createObjectURL(originalFile);
        setOriginalUrl(url);
        return () => URL.revokeObjectURL(url);
      }
      return undefined;
    }, [originalFile, result.category]);

    if (result.category === 'document' || result.category === 'archive') {
      return null;
    }

    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Preview</h3>

        {result.category === 'image' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {originalUrl && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Original</p>
                <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-950 flex items-center justify-center max-h-72">
                  <img src={originalUrl} alt="Original preview" className="max-h-72 w-auto object-contain" />
                </div>
              </div>
            )}
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-blue-600 dark:text-blue-400">Compressed</p>
              <div className="overflow-hidden rounded-xl border border-blue-200 dark:border-blue-900/60 bg-slate-100 dark:bg-slate-950 flex items-center justify-center max-h-72">
                <img src={result.downloadUrl} alt="Compressed preview" className="max-h-72 w-auto object-contain" />
              </div>
            </div>
          </div>
        )}

        {result.category === 'video' && (
          <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-black">
            <video src={result.downloadUrl} controls className="max-h-80 w-full object-contain" />
          </div>
        )}

        {result.category === 'pdf' && (
          <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-950 h-96">
            <iframe title="Compressed PDF preview" src={result.downloadUrl} className="h-full w-full" />
          </div>
        )}
      </div>
    );
  };
})();
