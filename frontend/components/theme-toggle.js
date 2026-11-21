/**
 * CITADEL Theme Controller
 * Supports Dark (default) and Light themes persisted in localStorage.
 */

const STORAGE_KEY = "citadel_theme";

export function getCurrentTheme() {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "light" ? "light" : "dark";
}

export function applyTheme(theme) {
  const resolved = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", resolved);
  try {
    localStorage.setItem(STORAGE_KEY, resolved);
  } catch (_err) {
    // Ignore storage quota / privacy mode errors
  }
  window.dispatchEvent(new CustomEvent("citadel:themechange", { detail: { theme: resolved } }));
  updateThemeToggleButtons(resolved);
  return resolved;
}

export function toggleTheme() {
  return applyTheme(getCurrentTheme() === "dark" ? "light" : "dark");
}

function sunIconSvg() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4"></circle>
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"></path>
  </svg>`;
}

function moonIconSvg() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
  </svg>`;
}

export function renderThemeToggleButton() {
  const theme = getCurrentTheme();
  const nextLabel = theme === "dark" ? "Light" : "Dark";
  const icon = theme === "dark" ? sunIconSvg() : moonIconSvg();
  return `
    <button
      type="button"
      id="citadel-theme-toggle"
      class="theme-toggle-btn"
      data-theme-toggle
      aria-label="Switch to ${nextLabel} Theme"
      title="Switch to ${nextLabel} Theme"
    >
      ${icon}
      <span class="theme-toggle-label">${nextLabel}</span>
    </button>
  `;
}

export function updateThemeToggleButtons(theme) {
  const nextLabel = theme === "dark" ? "Light" : "Dark";
  const icon = theme === "dark" ? sunIconSvg() : moonIconSvg();
  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.setAttribute("aria-label", `Switch to ${nextLabel} Theme`);
    btn.setAttribute("title", `Switch to ${nextLabel} Theme`);
    btn.innerHTML = `${icon}<span class="theme-toggle-label">${nextLabel}</span>`;
  });
}

export function bindThemeToggles() {
  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => toggleTheme());
  });
}
