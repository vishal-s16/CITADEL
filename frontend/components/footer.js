/**
 * CITADEL Consistent Footer Component
 */

export function renderFooter(container) {
  if (!container) return;

  container.innerHTML = `
    <div class="container">
      <div class="footer-grid">
        <div>
          <a href="/" data-link class="nav-brand" aria-label="CITADEL Home">
            <span class="nav-emblem-plate">
              <img src="/assets/logos/citadel_intrologo.jpeg" alt="CITADEL Emblem" />
            </span>
            <span class="nav-wordmark-plate">
              <img src="/assets/logos/citadel_logo.jpeg" alt="CITADEL" />
            </span>
          </a>
          <p class="footer-brand-desc">
            A centralized, modular digital platform engineered to unite independent security utilities and practical digital tools inside one unified workspace.
          </p>
        </div>

        <div>
          <h3 class="footer-heading">Platform</h3>
          <ul class="footer-links">
            <li><a href="/" data-link>Home</a></li>
            <li><a href="/tools" data-link>Tools Library</a></li>
            <li><a href="/about" data-link>About Us</a></li>
          </ul>
        </div>

        <div>
          <h3 class="footer-heading">Information</h3>
          <ul class="footer-links">
            <li><a href="/credits" data-link>Credits</a></li>
            <li><a href="/contact" data-link>Contact</a></li>
            <li><a href="/policy" data-link>Policy</a></li>
          </ul>
        </div>
      </div>

      <div class="footer-bottom">
        <span>&copy; 2026 CITADEL. All Rights Reserved.</span>
        <span class="mono">Modular Security &amp; Utility Platform</span>
      </div>
    </div>
  `;
}
