/**
 * CITADEL Tools Library Page
 * Dynamically retrieves registered modules from /api/modules so future
 * modules appear automatically without modifying this page's layout.
 */

import { renderToolCard } from "../components/tool-card.js";

export async function renderToolsPage(container) {
  document.title = "Tools Library — CITADEL";

  container.innerHTML = `
    <section class="page-header">
      <div class="container">
        <div class="page-kicker mono">Centralized Tool Library</div>
        <h1 class="page-title">CITADEL Tools</h1>
        <p class="page-subtitle">
          Access independent, production-ready digital utilities directly from one unified interface. No login required.
        </p>
      </div>
    </section>

    <section class="container" style="padding-bottom: 3rem;">
      <div id="tools-library-status" class="alert alert-info hidden" role="status"></div>
      <div id="tools-library-error" class="alert alert-error hidden" role="alert"></div>
      <div id="tools-grid" class="tools-grid">
        <div class="card">
          <p class="mono" style="font-size: 0.88rem;">Loading registered modules...</p>
        </div>
      </div>
    </section>
  `;

  const gridEl = container.querySelector("#tools-grid");
  const errorEl = container.querySelector("#tools-library-error");

  try {
    const res = await fetch("/api/modules");
    const data = await res.json();

    if (!res.ok || !data.ok || !Array.isArray(data.modules)) {
      throw new Error(data.message || "Unable to load registered modules.");
    }

    if (data.modules.length === 0) {
      gridEl.innerHTML = `
        <div class="card">
          <h3>No Modules Registered</h3>
          <p>No active tool modules are currently registered on this Citadel instance.</p>
        </div>
      `;
      return;
    }

    gridEl.innerHTML = data.modules.map((mod) => renderToolCard(mod)).join("");
  } catch (err) {
    gridEl.innerHTML = "";
    errorEl.textContent = err.message || "Failed to connect to the Citadel module registry.";
    errorEl.classList.remove("hidden");
  }
}
