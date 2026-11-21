/**
 * CITADEL Reusable Tool Card Component
 * Dynamically renders any registered module from the centralized module registry.
 */

const ICON_MAP = {
  "shield-layers": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    <path d="M9 12l2 2 4-4"></path>
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
