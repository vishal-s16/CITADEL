/**
 * CITADEL Consistent Navigation Bar
 * Navigation items: Home, Tools, About Us, Credits, Contact, Policy
 */

import { bindThemeToggles, renderThemeToggleButton } from "./theme-toggle.js";

const NAV_ITEMS = [
  { label: "Home", path: "/" },
  { label: "Tools", path: "/tools" },
  { label: "About Us", path: "/about" },
  { label: "Credits", path: "/credits" },
  { label: "Contact", path: "/contact" },
  { label: "Policy", path: "/policy" },
];

function isPathActive(itemPath, currentPath) {
  if (itemPath === "/") return currentPath === "/";
  return currentPath === itemPath || currentPath.startsWith(itemPath + "/");
}

export function renderNavbar(container, currentPath) {
  if (!container) return;

  const desktopLinks = NAV_ITEMS.map(
    (item) => `
      <li>
        <a href="${item.path}" data-link class="nav-link ${isPathActive(item.path, currentPath) ? "active" : ""}">
          ${item.label}
        </a>
      </li>`
  ).join("");

  const mobileLinks = NAV_ITEMS.map(
    (item) => `
      <li>
        <a href="${item.path}" data-link class="nav-link ${isPathActive(item.path, currentPath) ? "active" : ""}">
          ${item.label}
        </a>
      </li>`
  ).join("");

  container.innerHTML = `
    <nav class="navbar-inner" aria-label="Primary Navigation">
      <a href="/" data-link class="nav-brand" aria-label="CITADEL Home">
        <span class="nav-emblem-plate">
          <img src="/assets/logos/citadel_intrologo.jpeg" alt="CITADEL Emblem" />
        </span>
        <span class="nav-wordmark-plate">
          <img src="/assets/logos/citadel_logo.jpeg" alt="CITADEL" />
        </span>
      </a>

      <ul class="nav-links">${desktopLinks}</ul>

      <div class="nav-actions">
        ${renderThemeToggleButton()}
        <button
          type="button"
          id="mobile-menu-toggle"
          class="mobile-menu-btn"
          aria-expanded="false"
          aria-controls="mobile-nav-drawer"
          aria-label="Toggle Navigation Menu"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
      </div>
    </nav>

    <div id="mobile-nav-drawer" class="mobile-drawer">
      <ul class="mobile-nav-list">${mobileLinks}</ul>
    </div>
  `;

  bindThemeToggles();

  const menuBtn = container.querySelector("#mobile-menu-toggle");
  const drawer = container.querySelector("#mobile-nav-drawer");
  if (menuBtn && drawer) {
    menuBtn.addEventListener("click", () => {
      const open = drawer.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", String(open));
    });
    drawer.querySelectorAll("a[data-link]").forEach((a) => {
      a.addEventListener("click", () => {
        drawer.classList.remove("open");
        menuBtn.setAttribute("aria-expanded", "false");
      });
    });
  }
}
