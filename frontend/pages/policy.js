/**
 * CITADEL Policy Page
 * Accurately reflects the actual technical implementation without exaggerated claims.
 */

export function renderPolicyPage(container) {
  document.title = "Policy — CITADEL";

  container.innerHTML = `
    <section class="page-header">
      <div class="container container-narrow">
        <div class="page-kicker mono">Transparency &amp; Technical Standards</div>
        <h1 class="page-title">Platform Policies</h1>
        <p class="page-subtitle">
          Clear, implementation-accurate policies covering privacy, file handling, encryption, and operational limitations of CITADEL.
        </p>
      </div>
    </section>

    <section class="container container-narrow" style="padding-bottom: 3.5rem;">
      <div class="policy-stack">
        <article class="card policy-card">
          <h2><span class="policy-num mono">01</span> Privacy Policy</h2>
          <p>
            CITADEL does not require user accounts, login credentials, or registration to access its tools. The platform does not collect personal profiles, advertising identifiers, or behavioral tracking cookies.
          </p>
          <p>
            Your browser's local storage (<span class="mono">localStorage</span>) is used solely to remember your selected Dark/Light theme and music player volume preference locally on your device.
          </p>
        </article>

        <article class="card policy-card">
          <h2><span class="policy-num mono">02</span> Data Handling Policy</h2>
          <p>
            Files uploaded to the Steganography System are processed directly in server memory during the active encoding or extraction request.
          </p>
          <ul>
            <li><strong>Temporary In-Memory Caching:</strong> Generated encoded PNG images and extracted file download sessions are stored temporarily in a bounded in-memory cache (maximum 20 active sessions, 1-hour expiration TTL) so your browser can download the results.</li>
            <li><strong>No Permanent Disk Storage:</strong> Uploaded payloads and generated outputs are not written to permanent database or disk storage by the application. Restarting the server or letting the 1-hour TTL expire removes cached items from memory.</li>
          </ul>
        </article>

        <article class="card policy-card">
          <h2><span class="policy-num mono">03</span> File Processing Policy</h2>
          <p>
            The Steganography System processes container images and payload files using the following verified pipeline:
          </p>
          <ul>
            <li>Container images in PNG or JPEG/JPG format are validated and converted to lossless RGB PNG format before embedding.</li>
            <li>Selected payload files are serialized with their original filenames, extensions, and per-file plus overall SHA-256 digests, then compressed using <span class="mono">zlib</span>.</li>
            <li>The binary envelope includes a fixed 28-byte header with a <span class="mono">UISTEG01</span> signature and a CRC32 header checksum, embedded into the Least Significant Bits (LSB) of the RGB pixel channels.</li>
            <li>During extraction, the header CRC32 and payload SHA-256 checksums are verified before returning the recovered files.</li>
          </ul>
        </article>

        <article class="card policy-card">
          <h2><span class="policy-num mono">04</span> Security Policy</h2>
          <p>
            When password protection is enabled in the Steganography System, the compressed payload is encrypted with <strong>AES-256-GCM</strong> (authenticated encryption) using a 256-bit key derived via <strong>PBKDF2-HMAC-SHA256</strong> (200,000 iterations) with a freshly generated random 16-byte salt and 12-byte nonce for every encoding operation.
          </p>
          <p>
            While these cryptographic mechanisms protect payload confidentiality and detect tampering when a strong password is used, CITADEL does not claim to guarantee complete anonymity, absolute security, or formal regulatory certifications. Users handling highly sensitive material should operate CITADEL in a trusted environment and use strong, unique passwords.
          </p>
        </article>

        <article class="card policy-card">
          <h2><span class="policy-num mono">05</span> Acceptable Use Policy</h2>
          <p>
            You agree to use CITADEL and its modules only for lawful, authorized purposes. You must not use the platform to conceal malware, distribute illegal material, infringe intellectual property rights, or bypass lawful organizational security controls.
          </p>
        </article>

        <article class="card policy-card">
          <h2><span class="policy-num mono">06</span> Disclaimer &amp; Steganography Limitations</h2>
          <p>
            Image-based LSB steganography has strict technical constraints that users should understand before relying on encoded files:
          </p>
          <ul>
            <li><strong>Lossless PNG Required:</strong> Encoded output images must remain unmodified, lossless PNG files.</li>
            <li><strong>Fragility to Recompression &amp; Editing:</strong> Converting an encoded PNG to JPEG/WebP, resizing, cropping, applying filters, or sharing the image through messaging apps or social networks that recompress images will permanently destroy the hidden LSB data.</li>
            <li><strong>Capacity Limits:</strong> Maximum raw capacity is bounded by image dimensions (<span class="mono">(Width &times; Height &times; 3) / 8</span> bytes minus header and metadata overhead).</li>
            <li><strong>Detection Scope:</strong> Extraction only recognizes payloads created with this system's <span class="mono">UISTEG01</span> envelope format.</li>
          </ul>
          <p>
            Always keep a separate backup of important files and test extraction before relying on an encoded image. CITADEL is provided as-is without warranties of any kind.
          </p>
        </article>
      </div>
    </section>
  `;
}
