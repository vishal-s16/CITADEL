/**
 * CITADEL Reusable Tool Card Component
 * Dynamically renders any registered module from the centralized module registry.
 */

const ICON_MAP = {
  "shield-layers": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    <path d="M9 12l2 2 4-4"></path>
  </svg>`,
  "file-text": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
    <line x1="16" y1="13" x2="8" y2="13"></line>
    <line x1="16" y1="17" x2="8" y2="17"></line>
    <polyline points="10 9 9 9 8 9"></polyline>
  </svg>`,
  compress: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polyline points="4 14 10 14 10 20"></polyline>
    <polyline points="20 10 14 10 14 4"></polyline>
    <line x1="14" y1="10" x2="21" y2="3"></line>
    <line x1="3" y1="21" x2="10" y2="14"></line>
  </svg>`,
  default: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <rect x="3" y="3" width="18" height="18" rx="3"></rect>
    <path d="M9 9h6v6H9z"></path>
  </svg>`,
};

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function renderToolCard(module) {
  const iconSvg = ICON_MAP[module.icon] || ICON_MAP.default;
  const isAvailable = String(module.status).toLowerCase() === "available";
  const statusClass = isAvailable ? "badge-success" : "badge-info";

  const capabilitiesHtml =
    Array.isArray(module.capabilities) && module.capabilities.length > 0
      ? `<ul class="tool-capabilities">
          ${module.capabilities.map((cap) => `<li>${escapeHtml(cap)}</li>`).join("")}
        </ul>`
      : "";

  return `
    <article class="tool-card" data-module-id="${escapeHtml(module.module_id)}">
      <div>
        <div class="tool-card-top">
          <div class="feature-icon">${iconSvg}</div>
          <span class="badge ${statusClass}">
            <span class="status-dot"></span>
            ${escapeHtml(module.status)}
          </span>
        </div>

        <div class="tool-card-code mono">${escapeHtml(module.code || "MODULE")}</div>
        <h2 class="tool-card-title">${escapeHtml(module.name)}</h2>
        <div class="tool-card-category">${escapeHtml(module.category)}</div>
        <p class="tool-card-desc" style="margin-top: 0.7rem;">${escapeHtml(module.description)}</p>
      </div>

      ${capabilitiesHtml}

      <div class="tool-card-footer">
        <span class="mono" style="font-size: 0.78rem; color: var(--text-muted);">v${escapeHtml(module.version || "1.0.0")}</span>
        <a href="${escapeHtml(module.entry_route)}" data-link class="btn btn-primary btn-sm">
          Launch Tool &rarr;
        </a>
      </div>
    </article>
  `;
}
