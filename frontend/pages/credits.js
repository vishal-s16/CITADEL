/**
 * CITADEL Credits Page
 * Displays exact contributor credits with a clean, minimal layout.
 */

export function renderCreditsPage(container) {
  document.title = "Credits — CITADEL";

  container.innerHTML = `
    <section class="page-header">
      <div class="container">
        <div class="page-kicker mono">Acknowledgments</div>
        <h1 class="page-title">Credits</h1>
        <p class="page-subtitle">
          The people behind the development, support, and soundtrack of CITADEL.
        </p>
      </div>
    </section>

    <section class="container" style="padding-bottom: 3.5rem;">
      <div class="credits-grid">
        <article class="card credit-card">
          <div class="credit-role mono">Developed by</div>
          <h2 class="credit-name">Vishal S</h2>
        </article>

        <article class="card credit-card">
          <div class="credit-role mono">Helped by</div>
          <h2 class="credit-name">Vidhya M K</h2>
        </article>

        <article class="card credit-card">
          <div class="credit-role mono">Music by</div>
          <h2 class="credit-name">Keerthi Vasan</h2>
        </article>
      </div>
    </section>
  `;
}
