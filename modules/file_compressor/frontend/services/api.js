window.UFC = window.UFC || {};

(function () {
  const API_BASE = '/api/modules/compressor';

  async function uploadToServer(file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok || !data.success || !data.job) {
      throw new Error(data.error || 'File upload failed on server.');
    }
    return data.job.jobId;
  }

  window.UFC.cleanupServerJob = async function cleanupServerJob(jobId) {
    await fetch(`${API_BASE}/cleanup/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
  };

  window.UFC.compressOnServer = async function compressOnServer(
    file,
    targetSizeBytes,
    settings,
    onProgress
  ) {
    onProgress(10, 'Uploading file to secure temporary storage');
    const jobId = await uploadToServer(file);

    onProgress(20, 'Starting server-side compression');
    const startRes = await fetch(`${API_BASE}/compress?async=true`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jobId, targetSizeBytes, settings }),
    });
    const startData = await startRes.json();
    if (!startRes.ok || !startData.success) {
      await window.UFC.cleanupServerJob(jobId).catch(() => {});
      throw new Error(startData.error || 'Failed to start compression job.');
    }

    while (true) {
      await new Promise((r) => setTimeout(r, 400));
      const statusRes = await fetch(`${API_BASE}/status/${encodeURIComponent(jobId)}`);
      const statusData = await statusRes.json();

      if (!statusRes.ok || !statusData.success || !statusData.job) {
        throw new Error(statusData.error || 'Lost connection to compression job.');
      }

      const job = statusData.job;
      onProgress(job.progress, job.stage);

      if (job.status === 'failed') {
        throw new Error(job.error || 'Server compression failed.');
      }

      if (job.status === 'completed') {
        return {
          jobId: job.jobId,
          originalName: job.originalName,
          outputName: job.outputName,
          format: job.format,
          category: job.category,
          originalSize: job.originalSize,
          compressedSize: job.compressedSize ?? job.originalSize,
          spaceSaved: job.spaceSaved ?? 0,
          reductionPercent: job.reductionPercent ?? 0,
          targetSizeBytes: job.targetSizeBytes,
          targetAchieved: job.targetAchieved,
          warning: job.warning,
          engine: 'server',
          downloadUrl: `${API_BASE}/download/${encodeURIComponent(job.jobId)}`,
          status: 'completed',
        };
      }
    }
  };
})();
