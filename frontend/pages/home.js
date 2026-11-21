/**
 * CITADEL Home Page
 * Features: Hero with original Citadel logos, cybersecurity animated canvas,
 * tagline, CTA buttons, synced soundtrack trigger, and platform architecture highlights.
 */

let animationFrameId = null;

function cleanupHeroAnimation() {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
}

function initCyberGridCanvas(canvas) {
  if (!canvas) return () => {};
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};

  let width = 0;
  let height = 0;
  const nodes = [];
  const NODE_COUNT = 34;

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    width = canvas.width = Math.max(1, Math.floor(rect.width));
    height = canvas.height = Math.max(1, Math.floor(rect.height));
  }

  resize();
  for (let i = 0; i < NODE_COUNT; i++) {
    nodes.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      r: 1.4 + Math.random() * 1.4,
    });
  }

  function getThemeColors() {
    const styles = getComputedStyle(document.documentElement);
    return {
      line: styles.getPropertyValue("--grid-line").trim() || "rgba(56, 189, 248, 0.08)",
      node: styles.getPropertyValue("--grid-node").trim() || "rgba(56, 189, 248, 0.3)",
    };
  }

  let colors = getThemeColors();
  const onTheme = () => {
    colors = getThemeColors();
  };
  window.addEventListener("citadel:themechange", onTheme);
  window.addEventListener("resize", resize);

  function frame() {
    ctx.clearRect(0, 0, width, height);

    // Subtle geometric grid
    ctx.strokeStyle = colors.line;
    ctx.lineWidth = 1;
    const step = 56;
    ctx.beginPath();
    for (let x = 0; x < width; x += step) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
    }
    for (let y = 0; y < height; y += step) {
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
    }
    ctx.stroke();

    // Moving security nodes and connections
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      n.x += n.vx;
      n.y += n.vy;
      if (n.x < 0 || n.x > width) n.vx *= -1;
      if (n.y < 0 || n.y > height) n.vy *= -1;

      for (let j = i + 1; j < nodes.length; j++) {
        const m = nodes[j];
        const dx = n.x - m.x;
        const dy = n.y - m.y;
        const dist = Math.hypot(dx, dy);
        if (dist < 145) {
          ctx.strokeStyle = colors.line;
          ctx.beginPath();
          ctx.moveTo(n.x, n.y);
          ctx.lineTo(m.x, m.y);
          ctx.stroke();
        }
      }

      ctx.fillStyle = colors.node;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();
    }

    animationFrameId = requestAnimationFrame(frame);
  }

  frame();

  return () => {
    cleanupHeroAnimation();
    window.removeEventListener("citadel:themechange", onTheme);
    window.removeEventListener("resize", resize);
  };
}

export function renderHomePage(container) {
  document.title = "CITADEL — One Platform. Multiple Possibilities.";

  const isPlaying = typeof window.citadelIsMusicPlaying === "function" && window.citadelIsMusicPlaying();

  container.innerHTML = `
    <section class="hero-section">
      <canvas id="hero-cyber-canvas" class="hero-canvas" aria-hidden="true"></canvas>
      <div class="container">
        <div class="hero-content">
          <div class="hero-brand-showcase">
            <img src="/assets/logos/citadel_intrologo.jpeg" alt="CITADEL Skull Emblem" class="hero-emblem" />
            <span class="hero-brand-divider" aria-hidden="true"></span>
            <img src="/assets/logos/citadel_logo.jpeg" alt="CITADEL Wordmark" class="hero-wordmark" />
          </div>

          <div class="hero-eyebrow mono">
            <span class="hero-eyebrow-dot"></span>
            Centralized Multi-Tool Platform
          </div>

          <h1 class="hero-title">CITADEL</h1>
          <p class="hero-tagline">One Platform. Multiple Possibilities.</p>
          <p class="hero-description">
            Your centralized destination for powerful digital tools, security utilities, and intelligent solutions.
          </p>

          <div class="hero-cta-group">
            <a href="/tools" data-link class="btn btn-primary btn-lg">Explore Tools &rarr;</a>
            <a href="/about" data-link class="btn btn-secondary btn-lg">Discover Citadel</a>
          </div>

          <div class="hero-audio-callout">
            <span>Soundtrack by Keerthi Vasan &middot;</span>
            <button type="button" id="hero-music-toggle">
              ${isPlaying ? "Pause Theme" : "Play Theme"}
            </button>
          </div>
        </div>
      </div>
    </section>

    <section class="page-section">
      <div class="container">
        <div class="grid-3">
          <div class="card card-interactive">
            <div class="feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <rect x="3" y="3" width="7" height="7" rx="1.5"></rect>
                <rect x="14" y="3" width="7" height="7" rx="1.5"></rect>
                <rect x="3" y="14" width="7" height="7" rx="1.5"></rect>
                <rect x="14" y="14" width="7" height="7" rx="1.5"></rect>
              </svg>
            </div>
            <h3>Modular Architecture</h3>
            <p>
              Every utility runs as an independent module registered through Citadel's centralized module manager, enabling seamless future expansion.
            </p>
          </div>

          <div class="card card-interactive">
            <div class="feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                <path d="M9 12l2 2 4-4"></path>
              </svg>
            </div>
            <h3>Direct Access, Zero Friction</h3>
            <p>
              Launch security and digital tools immediately without account creation, registration walls, or unnecessary distractions.
            </p>
          </div>

          <div class="card card-interactive">
            <div class="feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <polyline points="16 18 22 12 16 6"></polyline>
                <polyline points="8 6 2 12 8 18"></polyline>
              </svg>
            </div>
            <h3>Built for Precision</h3>
            <p>
              Backed by dedicated FastAPI services, clean validation, and integrity-verified processing pipelines tailored to each tool.
            </p>
          </div>
        </div>
      </div>
    </section>
  `;

  const heroBtn = container.querySelector("#hero-music-toggle");
  const syncHeroMusicBtn = (evt) => {
    if (!heroBtn) return;
    heroBtn.textContent = evt.detail && evt.detail.isPlaying ? "Pause Theme" : "Play Theme";
  };
  if (heroBtn) {
    heroBtn.addEventListener("click", () => {
      if (typeof window.citadelToggleMusic === "function") {
        window.citadelToggleMusic();
      }
    });
  }
  window.addEventListener("citadel:musicstate", syncHeroMusicBtn);

  const stopCanvas = initCyberGridCanvas(container.querySelector("#hero-cyber-canvas"));

  return () => {
    stopCanvas();
    window.removeEventListener("citadel:musicstate", syncHeroMusicBtn);
  };
}
