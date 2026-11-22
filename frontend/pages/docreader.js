/**
 * CITADEL Module 02 — DocReader Interface
 * Embeds the integrated DocReader workspace inside CITADEL's SPA shell
 * and synchronizes CITADEL's Dark/Light theme automatically.
 */

export function renderDocReaderPage(container) {
  document.title = "DocReader — CITADEL";

  container.innerHTML = `
    <div class="container">
      <div class="module-topbar">
        <div>
          <div class="module-breadcrumb">
            <a href="/tools" data-link class="btn btn-ghost btn-sm">&larr; Return to Citadel Tools</a>
            <span class="badge badge-info mono">MODULE 02</span>
          </div>
          <h1 style="font-size: 1.7rem; font-weight: 800; margin-top: 0.65rem;">DocReader</h1>
          <p style="font-size: 0.9rem; color: var(--text-secondary);">
            All-in-One AI Document Reader &middot; PDF, Word, Excel, PowerPoint, OCR, Full-Text Search &amp; TTS
          </p>
        </div>
        <a href="/module-ui/docreader/" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">
          Open Fullscreen &#8599;
        </a>
      </div>

      <div class="module-embed-shell">
        <iframe
          id="docreader-module-frame"
          class="module-embed-frame"
          src="/module-ui/docreader/"
          title="CITADEL Module 02 — DocReader"
          loading="eager"
        ></iframe>
      </div>
    </div>
  `;

  const iframe = container.querySelector("#docreader-module-frame");

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
