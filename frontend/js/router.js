/**
 * CITADEL SPA Router & Application Bootstrap
 * Keeps the persistent music player mounted across internal page transitions
 * so background audio continues uninterrupted.
 */

import { renderNavbar } from "../components/navbar.js";
import { renderFooter } from "../components/footer.js";
import { initMusicPlayer } from "../components/music-player.js";
import { renderHomePage } from "../pages/home.js";
import { renderToolsPage } from "../pages/tools.js";
import { renderSteganographyPage } from "../pages/steganography.js";
import { renderAboutPage } from "../pages/about.js";
import { renderCreditsPage } from "../pages/credits.js";
import { renderContactPage } from "../pages/contact.js";
import { renderPolicyPage } from "../pages/policy.js";

const ROUTES = {
  "/": renderHomePage,
  "/tools": renderToolsPage,
  "/tools/steganography": renderSteganographyPage,
  "/about": renderAboutPage,
  "/credits": renderCreditsPage,
  "/contact": renderContactPage,
  "/policy": renderPolicyPage,
};

let currentCleanup = null;

function normalizePath(pathname) {
  if (!pathname || pathname === "/") return "/";
  return pathname.replace(/\/+$/, "") || "/";
}

async function renderRoute(pathname) {
  const path = normalizePath(pathname);
  const navbarEl = document.getElementById("citadel-navbar");
  const viewEl = document.getElementById("app-view");

  if (typeof currentCleanup === "function") {
    try {
      currentCleanup();
    } catch (_err) {
      // ignore cleanup error
    }
    currentCleanup = null;
  }

  renderNavbar(navbarEl, path);

  const renderer = ROUTES[path];
  if (renderer) {
    const maybeCleanup = await renderer(viewEl);
    if (typeof maybeCleanup === "function") {
      currentCleanup = maybeCleanup;
    }
  } else {
    document.title = "Page Not Found — CITADEL";
    viewEl.innerHTML = `
      <section class="page-section">
        <div class="container container-narrow">
          <div class="card" style="text-align: center; padding: 3rem 1.5rem;">
            <div class="page-kicker mono">404</div>
            <h1 style="margin-bottom: 0.6rem;">Page Not Found</h1>
            <p style="margin-bottom: 1.5rem;">The requested CITADEL route does not exist.</p>
            <a href="/" data-link class="btn btn-primary">Return Home</a>
          </div>
        </div>
      </section>
    `;
  }

  window.scrollTo({ top: 0, behavior: "instant" });
}

export function navigateTo(url) {
  const target = new URL(url, window.location.origin);
  if (target.origin !== window.location.origin) {
    window.location.href = target.href;
    return;
  }
  const nextPath = normalizePath(target.pathname);
  if (nextPath !== normalizePath(window.location.pathname)) {
    window.history.pushState({}, "", nextPath);
  }
  renderRoute(nextPath);
}

function bootstrap() {
  renderFooter(document.getElementById("citadel-footer"));
  initMusicPlayer(document.getElementById("citadel-music-player"));

  // Intercept internal SPA navigation clicks
  document.addEventListener("click", (e) => {
    const link = e.target.closest("a[data-link]");
    if (!link) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || link.target === "_blank") return;
    e.preventDefault();
    navigateTo(link.getAttribute("href"));
  });

  window.addEventListener("popstate", () => {
    renderRoute(window.location.pathname);
  });

  renderRoute(window.location.pathname);
}

bootstrap();
