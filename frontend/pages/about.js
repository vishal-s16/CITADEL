/**
 * CITADEL About Us Page
 */

export function renderAboutPage(container) {
  document.title = "About Us — CITADEL";

  container.innerHTML = `
    <section class="page-header">
      <div class="container">
        <div class="page-kicker mono">Platform Overview</div>
        <h1 class="page-title">About CITADEL</h1>
        <p class="page-subtitle">
          Citadel is a centralized digital platform designed to bring multiple useful tools together in one accessible environment.
        </p>
      </div>
    </section>

    <section class="container" style="padding-bottom: 3rem;">
      <div class="card" style="margin-bottom: 1.5rem;">
        <h3>Project Introduction</h3>
        <p style="margin-top: 0.5rem;">
          Citadel is a centralized digital platform designed to bring multiple useful tools together in one accessible environment.
          Our goal is to create a scalable ecosystem where users can access different utilities without switching between multiple platforms.
          Citadel follows a modular architecture, allowing independent tools to be developed, integrated, and expanded over time.
        </p>
      </div>

      <div class="grid-2" style="margin-bottom: 1.5rem;">
        <div class="card">
          <h3>Vision</h3>
          <p style="margin-top: 0.45rem;">
            To serve as a dependable, distraction-free command center where practical security utilities and digital tools coexist under a consistent, high-clarity interface.
          </p>
        </div>
        <div class="card">
          <h3>Mission</h3>
          <p style="margin-top: 0.45rem;">
            Deliver focused, well-engineered tools with transparent technical foundations, direct browser access, and clean architectural separation so each capability can evolve independently.
          </p>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <h3>Platform Capabilities</h3>
          <ul style="padding-left: 1.2rem; margin-top: 0.65rem; color: var(--text-secondary); font-size: 0.94rem;">
            <li style="margin-bottom: 0.4rem;">Unified navigation, responsive layouts, and synchronized Dark and Light themes.</li>
            <li style="margin-bottom: 0.4rem;">Centralized module registry serving active tools dynamically to the Tool Library.</li>
            <li style="margin-bottom: 0.4rem;">Direct access to tools without mandatory account sign-up or login barriers.</li>
            <li>Dedicated FastAPI backend integration for real server-side file processing.</li>
          </ul>
        </div>
        <div class="card">
          <h3>Modular Development Approach</h3>
          <p style="margin-top: 0.45rem;">
            Each tool inside Citadel is built and maintained as an isolated module with its own backend router, validation rules, and user interface.
            Adding a new module only requires registering its metadata and API router in the module manager—without rewriting Citadel's core architecture or redesigning the platform.
          </p>
        </div>
      </div>
    </section>
  `;
}
