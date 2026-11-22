/**
 * CITADEL Module 03 — Universal File Compressor Interface
 * Embeds the integrated Universal File Compressor workspace inside CITADEL's SPA shell
 * and synchronizes CITADEL's Dark/Light theme automatically.
 */

export function renderCompressorPage(container) {
  document.title = "Universal File Compressor — CITADEL";

  container.innerHTML = `
    <div class="container">
      <div class="module-topbar">
        <div>
          <div class="module-breadcrumb">
            <a href="/tools" data-link class="btn btn-ghost btn-sm">&larr; Return to Citadel Tools</a>
            <span class="badge badge-info mono">MODULE 03</span>
          </div>
          <h1 style="font-size: 1.7rem; font-weight: 800; margin-top: 0.65rem;">Universal File Compressor</h1>
          <p style="font-size: 0.9rem; color: var(--text-secondary);">
            Smart Hybrid Compression &middot; Images, PDFs, Office Docs, Audio, Video &amp; Archives
          </p>
        </div>
        <a href="/module-ui/compressor/" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">
          Open Fullscreen &#8599;
        </a>
      </div>

      <div class="module-embed-shell">
        <iframe
          id="compressor-module-frame"
          class="module-embed-frame"
          src="/module-ui/compressor/"
          title="CITADEL Module 03 — Universal File Compressor"
          loading="eager"
        ></iframe>
      </div>
    </div>
  `;

  const iframe = container.querySelector("#compressor-module-frame");

  function syncTheme() {
    if (!iframe || !iframe.contentWindow) return;
    const theme = document.documentElement.getAttribute("data-theme") || "dark";
    iframe.contentWindow.postMessage({ type: "citadel:theme", theme }, window.location.origin);
  }

  iframe.addEventListener("load", syncTheme);
  window.addEventListener("citadel:themechange", syncTheme);

  return () => {
    window.removeEventListener("citadel:themechange", syncTheme);
  };
}
