/**
 * CITADEL Contact Page
 * Provides direct mailto button, copy-to-clipboard button, and email composer.
 */

const CONTACT_EMAIL = "vishalsoundararajan16@gmail.com";

export function renderContactPage(container) {
  document.title = "Contact — CITADEL";

  container.innerHTML = `
    <section class="page-header">
      <div class="container">
        <div class="page-kicker mono">Get in Touch</div>
        <h1 class="page-title">Contact CITADEL</h1>
        <p class="page-subtitle">
          Questions, feedback, or module suggestions? Reach out directly via email.
        </p>
      </div>
    </section>

    <section class="container" style="padding-bottom: 3.5rem;">
      <div class="contact-grid">
        <div class="card">
          <h3>Direct Email</h3>
          <p style="margin-top: 0.4rem;">
            Use the address below or click the contact button to open your default email application.
          </p>

          <div class="email-box">
            <span id="contact-email-text" class="mono" style="font-weight: 600;">${CONTACT_EMAIL}</span>
          </div>

          <div class="contact-actions">
            <a href="mailto:${CONTACT_EMAIL}?subject=CITADEL%20Platform%20Inquiry" class="btn btn-primary">
              Open Email App
            </a>
            <button type="button" id="copy-email-btn" class="btn btn-secondary">
              Copy Email
            </button>
          </div>

          <div id="copy-feedback" class="alert alert-info hidden" role="status">
            Email address copied to clipboard.
          </div>
        </div>

        <div class="card">
          <h3>Compose Message</h3>
          <p style="margin-top: 0.4rem; margin-bottom: 1.15rem;">
            Draft your message here and launch it directly in your default mail client.
          </p>

          <form id="contact-mailto-form">
            <div class="form-group">
              <label for="contact-subject">Subject</label>
              <input
                type="text"
                id="contact-subject"
                class="form-control"
                placeholder="e.g., Feedback on Citadel Steganography System"
                required
              />
            </div>

            <div class="form-group">
              <label for="contact-message">Message</label>
              <textarea
                id="contact-message"
                class="form-control"
                rows="5"
                placeholder="Write your message..."
                required
              ></textarea>
            </div>

            <button type="submit" class="btn btn-primary">Compose in Email App &rarr;</button>
          </form>
        </div>
      </div>
    </section>
  `;

  const copyBtn = container.querySelector("#copy-email-btn");
  const copyFeedback = container.querySelector("#copy-feedback");

  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(CONTACT_EMAIL);
        copyFeedback.textContent = "Email address copied to clipboard.";
        copyFeedback.classList.remove("hidden");
        setTimeout(() => copyFeedback.classList.add("hidden"), 3000);
      } catch (_err) {
        // Fallback selection copy
        const temp = document.createElement("textarea");
        temp.value = CONTACT_EMAIL;
        document.body.appendChild(temp);
        temp.select();
        document.execCommand("copy");
        document.body.removeChild(temp);
        copyFeedback.textContent = "Email address copied to clipboard.";
        copyFeedback.classList.remove("hidden");
        setTimeout(() => copyFeedback.classList.add("hidden"), 3000);
      }
    });
  }

  const form = container.querySelector("#contact-mailto-form");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const subject = encodeURIComponent(container.querySelector("#contact-subject").value.trim());
      const body = encodeURIComponent(container.querySelector("#contact-message").value.trim());
      window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
    });
  }
}
