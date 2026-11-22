/**
 * CITADEL Module 01 — Steganography System Interface
 * Connected directly to the live FastAPI backend at /api/modules/steganography/*
 * Preserves 100% of the existing encoding, capacity analysis, AES-256-GCM encryption,
 * inspection, extraction, SHA-256 verification, and download workflows.
 */

const API_BASE = "/api/modules/steganography";

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes.toLocaleString()} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatAllUnits(units) {
  if (!units) return "—";
  return `${units.bytes.toLocaleString()} B (${units.kb} KB / ${units.mb} MB)`;
}

function getExtension(filename) {
  const idx = filename.lastIndexOf(".");
  if (idx <= 0 || idx === filename.length - 1) return "";
  return filename.slice(idx + 1).toLowerCase();
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export async function renderSteganographyPage(container) {
  document.title = "Steganography System — CITADEL";

  const state = {
    mode: "hide",
    stage: 1,
    containerFile: null,
    containerPreviewUrl: null,
    containerInfo: null,
    selectedCategory: null,
    allowedExtensions: [],
    payloadFiles: [],
    storageAnalysis: null,
    extractFile: null,
    extractPreviewUrl: null,
    extractInspection: null,
    extractInspectToken: null,
  };

  container.innerHTML = `
    <div class="container container-narrow">
      <div class="module-topbar">
        <div>
          <div class="module-breadcrumb">
            <a href="/tools" data-link class="btn btn-ghost btn-sm">&larr; Return to Citadel Tools</a>
            <span class="badge badge-info mono">MODULE 01</span>
          </div>
          <h1 style="font-size: 1.7rem; font-weight: 800; margin-top: 0.65rem;">Steganography System</h1>
          <p style="font-size: 0.9rem; color: var(--text-secondary);">
            RGB Least Significant Bit (LSB) embedding &middot; zlib compression &middot; Optional AES-256-GCM encryption
          </p>
        </div>

        <nav class="mode-tabs" aria-label="Steganography Mode">
          <button type="button" id="nav-hide-btn" class="mode-tab active" data-mode="hide">Hide Files</button>
          <button type="button" id="nav-extract-btn" class="mode-tab" data-mode="extract">Extract Files</button>
        </nav>
      </div>

      <!-- HIDE FILES PANEL -->
      <div id="hide-panel">
        <ol id="stepper" class="stepper" aria-label="Encoding workflow progress">
          <li class="stepper-item active" data-stage="1">
            <span class="stepper-num">1</span>
            <span class="stepper-label">Upload Image</span>
          </li>
          <li class="stepper-connector"></li>
          <li class="stepper-item" data-stage="2">
            <span class="stepper-num">2</span>
            <span class="stepper-label">Select Files</span>
          </li>
          <li class="stepper-connector"></li>
          <li class="stepper-item" data-stage="3">
            <span class="stepper-num">3</span>
            <span class="stepper-label">Generate PNG</span>
          </li>
        </ol>

        <!-- STAGE 1 -->
        <section id="stage-1" class="stage-panel active" aria-labelledby="stage1-heading">
          <div class="card">
            <div class="card-header">
              <span class="step-pill mono">Stage 1 of 3</span>
              <h2 id="stage1-heading">Upload Container Image</h2>
              <p>Select a PNG or JPEG/JPG image to serve as the lossless carrier container.</p>
            </div>

            <div id="image-dropzone" class="dropzone" tabindex="0" role="button" aria-label="Upload container image">
              <input type="file" id="image-file-input" accept=".png,.jpg,.jpeg,image/png,image/jpeg" hidden />
              <div class="dropzone-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
                  <rect x="3" y="3" width="18" height="18" rx="3"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5"></circle>
                  <path d="M21 15l-5-5L5 21"></path>
                </svg>
              </div>
              <p class="dropzone-title">Drag and drop your image here</p>
              <p class="dropzone-hint">Supports PNG, JPEG, and JPG &middot; JPEGs are automatically converted to lossless PNG</p>
              <button type="button" id="browse-image-btn" class="btn btn-secondary btn-sm">Browse Files</button>
            </div>

            <div id="stage1-error" class="alert alert-error hidden" role="alert"></div>

            <div id="image-preview-panel" class="image-preview-panel hidden">
              <div class="preview-thumb-wrap">
                <img id="container-preview-img" src="" alt="Container image preview" />
              </div>
              <div class="preview-details">
                <div class="detail-row">
                  <span class="detail-label">Filename</span>
                  <span id="img-meta-name" class="detail-value mono"></span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">Dimensions</span>
                  <span id="img-meta-dims" class="detail-value mono"></span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">Image Size</span>
                  <span id="img-meta-size" class="detail-value mono"></span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">Raw Capacity (RGB LSB)</span>
                  <span id="img-meta-capacity" class="detail-value mono accent-text"></span>
                </div>
                <div id="jpeg-notice" class="badge badge-info hidden" style="margin-top: 0.75rem;">
                  JPEG detected &mdash; will be converted to a lossless PNG container before embedding.
                </div>
                <div class="preview-actions">
                  <button type="button" id="change-image-btn" class="btn btn-ghost btn-sm">Change Image</button>
                </div>
              </div>
            </div>

            <div class="stage-footer">
              <span></span>
              <button type="button" id="stage1-continue-btn" class="btn btn-primary" disabled>
                Continue &rarr;
              </button>
            </div>
          </div>
        </section>

        <!-- STAGE 2 -->
        <section id="stage-2" class="stage-panel" aria-labelledby="stage2-heading">
          <div class="card">
            <div class="card-header">
              <span class="step-pill mono">Stage 2 of 3</span>
              <h2 id="stage2-heading">What type of file would you like to hide?</h2>
              <p>Choose a category below, then add one or more matching files.</p>
            </div>

            <div id="category-grid" class="category-grid" role="radiogroup" aria-label="File categories">
              <p class="mono" style="font-size: 0.85rem;">Loading categories...</p>
            </div>

            <div id="payload-upload-section" class="hidden">
              <div class="section-divider"></div>
              <div class="upload-section-header">
                <div>
                  <h3 id="selected-category-title">Upload Files</h3>
                  <p id="selected-category-hint" style="font-size: 0.85rem;"></p>
                </div>
                <button type="button" id="add-more-files-btn" class="btn btn-secondary btn-sm">
                  + Add Another File
                </button>
              </div>

              <div id="payload-dropzone" class="dropzone dropzone-compact" tabindex="0" role="button" aria-label="Upload files to hide">
                <input type="file" id="payload-file-input" multiple hidden />
                <div class="dropzone-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="12" y1="18" x2="12" y2="12"></line>
                    <line x1="9" y1="15" x2="15" y2="15"></line>
                  </svg>
                </div>
                <p class="dropzone-title">Drag and drop files here, or click to browse</p>
                <p id="payload-accept-hint" class="dropzone-hint"></p>
              </div>

              <div id="stage2-error" class="alert alert-error hidden" role="alert"></div>

              <div id="selected-files-container" class="file-list-wrap hidden">
                <div class="file-list-summary">
                  <span id="selected-files-count">0 files selected</span>
                  <span id="selected-files-total-size" class="mono accent-text">Total: 0 B</span>
                </div>
                <ul id="selected-files-list" class="file-list"></ul>
              </div>
            </div>

            <div class="stage-footer">
              <button type="button" id="stage2-back-btn" class="btn btn-ghost">&larr; Back</button>
              <button type="button" id="stage2-continue-btn" class="btn btn-primary" disabled>
                Review &amp; Continue &rarr;
              </button>
            </div>
          </div>
        </section>

        <!-- STAGE 3 -->
        <section id="stage-3" class="stage-panel" aria-labelledby="stage3-heading">
          <div class="card">
            <div class="card-header">
              <span class="step-pill mono">Stage 3 of 3</span>
              <h2 id="stage3-heading">Generate Hidden Image</h2>
              <p>Review storage capacity, optionally enable AES-256-GCM encryption, and embed your files.</p>
            </div>

            <div class="summary-grid">
              <div class="summary-box">
                <h3>Container Image</h3>
                <div class="detail-row">
                  <span class="detail-label">Original Name</span>
                  <span id="sum-img-name" class="detail-value mono"></span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">Dimensions</span>
                  <span id="sum-img-dims" class="detail-value mono"></span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">Image Size</span>
                  <span id="sum-img-size" class="detail-value mono"></span>
                </div>
              </div>

              <div class="summary-box">
                <h3>Files to Hide</h3>
                <div class="detail-row">
                  <span class="detail-label">Selected Files</span>
                  <span id="sum-file-count" class="detail-value mono"></span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">Total File Size</span>
                  <span id="sum-file-total" class="detail-value mono"></span>
                </div>
                <ul id="sum-file-names" class="compact-file-list"></ul>
              </div>
            </div>

            <div class="storage-box">
              <div class="storage-header">
                <h3>Storage Analysis</h3>
                <span id="storage-status-badge" class="badge">Calculating...</span>
              </div>

              <div class="capacity-bar-track" aria-hidden="true">
                <div id="capacity-bar-fill" class="capacity-bar-fill" style="width: 0%;"></div>
              </div>

              <div class="storage-metrics">
                <div class="metric-tile">
                  <span class="metric-label">Available Capacity</span>
                  <span id="cap-available" class="metric-value mono">&mdash;</span>
                </div>
                <div class="metric-tile">
                  <span class="metric-label">Required Storage</span>
                  <span id="cap-required" class="metric-value mono">&mdash;</span>
                </div>
                <div class="metric-tile">
                  <span class="metric-label">Remaining Capacity</span>
                  <span id="cap-remaining" class="metric-value mono">&mdash;</span>
                </div>
              </div>
            </div>

            <div class="encryption-box">
              <label class="toggle-row" for="enable-encryption-toggle">
                <div>
                  <span class="toggle-title">Enable Password Protection (AES-256-GCM)</span>
                  <span class="toggle-desc">Encrypts the compressed payload with PBKDF2-HMAC-SHA256 key derivation before embedding.</span>
                </div>
                <input type="checkbox" id="enable-encryption-toggle" class="toggle-checkbox" />
              </label>

              <div id="password-fields" class="password-fields hidden">
                <div class="form-group" style="margin-bottom: 0;">
                  <label for="encode-password">Password</label>
                  <input type="password" id="encode-password" class="form-control" placeholder="Create a strong password" autocomplete="new-password" />
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                  <label for="encode-password-confirm">Confirm Password</label>
                  <input type="password" id="encode-password-confirm" class="form-control" placeholder="Re-enter password" autocomplete="new-password" />
                </div>
              </div>
            </div>

            <div id="stage3-error" class="alert alert-error hidden" role="alert"></div>

            <div id="encoding-progress-panel" class="progress-panel hidden" aria-live="polite">
              <h3>Encoding Progress</h3>
              <ol id="encoding-steps-list" class="progress-steps">
                <li data-step="1"><span class="step-dot"></span>1. Preparing files.</li>
                <li data-step="2"><span class="step-dot"></span>2. Compressing files.</li>
                <li data-step="3"><span class="step-dot"></span>3. Encrypting files (if enabled).</li>
                <li data-step="4"><span class="step-dot"></span>4. Converting data into binary.</li>
                <li data-step="5"><span class="step-dot"></span>5. Embedding data into image.</li>
                <li data-step="6"><span class="step-dot"></span>6. Generating final PNG.</li>
              </ol>
            </div>

            <div class="stage-footer">
              <button type="button" id="stage3-back-btn" class="btn btn-ghost">&larr; Back</button>
              <button type="button" id="generate-btn" class="btn btn-primary btn-lg" disabled>
                Generate Hidden Image
              </button>
            </div>
          </div>
        </section>

        <!-- RESULT VIEW -->
        <section id="stage-result" class="stage-panel" aria-labelledby="result-heading">
          <div class="card">
            <div class="result-banner">
              <div class="result-check" aria-hidden="true">&#10003;</div>
              <h2 id="result-heading">Your Hidden Image Is Ready!</h2>
              <p>Your files have been losslessly embedded into a standard PNG image.</p>
            </div>

            <div class="comparison-grid">
              <div class="preview-card">
                <span class="badge">Original Image</span>
                <img id="result-original-img" src="" alt="Original container image preview" />
              </div>
              <div class="preview-card">
                <span class="badge badge-success">Encoded PNG Image</span>
                <img id="result-encoded-img" src="" alt="Encoded image preview" />
              </div>
            </div>

            <div class="result-stats-grid">
              <div class="metric-tile">
                <span class="metric-label">Original Image Size</span>
                <span id="res-orig-size" class="metric-value mono">&mdash;</span>
              </div>
              <div class="metric-tile">
                <span class="metric-label">Encoded Image Size</span>
                <span id="res-enc-size" class="metric-value mono">&mdash;</span>
              </div>
              <div class="metric-tile">
                <span class="metric-label">Hidden Files</span>
                <span id="res-file-count" class="metric-value mono">&mdash;</span>
              </div>
              <div class="metric-tile">
                <span class="metric-label">Total Hidden Data Size</span>
                <span id="res-data-size" class="metric-value mono">&mdash;</span>
              </div>
              <div class="metric-tile metric-wide">
                <span class="metric-label">Encoding Algorithm Used</span>
                <span id="res-algorithm" class="metric-value mono accent-text">&mdash;</span>
              </div>
            </div>

            <div class="result-actions">
              <a id="download-encoded-btn" href="#" download class="btn btn-primary btn-lg">
                Download Encoded PNG
              </a>
              <button type="button" id="start-new-btn" class="btn btn-secondary btn-lg">
                Start New Operation
              </button>
            </div>
          </div>
        </section>
      </div>

      <!-- EXTRACT FILES PANEL -->
      <section id="extract-panel" class="hidden" aria-labelledby="extract-heading">
        <div class="card">
          <div class="card-header">
            <span class="step-pill mono">Recovery &amp; Verification</span>
            <h2 id="extract-heading">Extract Hidden Files</h2>
            <p>Upload an encoded PNG image created with this system to inspect and recover its hidden files.</p>
          </div>

          <div id="extract-dropzone" class="dropzone" tabindex="0" role="button" aria-label="Upload encoded PNG image">
            <input type="file" id="extract-file-input" accept=".png,image/png" hidden />
            <div class="dropzone-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
            </div>
            <p class="dropzone-title">Drag and drop an encoded PNG image</p>
            <p class="dropzone-hint">Lossless PNG files only &middot; Automatically verifies header CRC32 and payload metadata</p>
            <button type="button" id="browse-extract-btn" class="btn btn-secondary btn-sm">Browse PNG Image</button>
          </div>

          <div id="extract-error" class="alert alert-error hidden" role="alert"></div>
          <div id="extract-info" class="alert alert-info hidden" role="status"></div>

          <div id="extract-inspect-panel" class="image-preview-panel hidden" style="margin-top: 1.15rem;">
            <div class="preview-thumb-wrap">
              <img id="extract-preview-img" src="" alt="Encoded PNG preview" />
            </div>
            <div class="preview-details">
              <div class="detail-row">
                <span class="detail-label">Filename</span>
                <span id="ext-meta-name" class="detail-value mono"></span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Dimensions</span>
                <span id="ext-meta-dims" class="detail-value mono"></span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Payload Status</span>
                <span id="ext-meta-status" class="detail-value"></span>
              </div>

              <div id="extract-password-wrap" class="form-group hidden" style="margin-top: 0.9rem; margin-bottom: 0;">
                <label for="extract-password">Payload Password</label>
                <input type="password" id="extract-password" class="form-control" placeholder="Enter password to decrypt hidden files" autocomplete="current-password" />
              </div>

              <div class="preview-actions">
                <button type="button" id="run-extract-btn" class="btn btn-primary btn-sm">Extract Files</button>
                <button type="button" id="reset-extract-btn" class="btn btn-ghost btn-sm">Choose Another Image</button>
              </div>
            </div>
          </div>

          <div id="extract-results-panel" class="hidden">
            <div class="section-divider"></div>
            <div class="extract-results-header">
              <div>
                <h3>Recovered Files</h3>
                <p id="extract-results-meta" style="font-size: 0.88rem;"></p>
              </div>
              <a id="download-all-zip-btn" href="#" download class="btn btn-primary btn-sm hidden">
                Download All as ZIP
              </a>
            </div>
            <div class="badge badge-success integrity-badge">
              &#10003; SHA-256 Integrity Verified &mdash; Byte-for-Byte Match
            </div>
            <ul id="extracted-files-list" class="file-list"></ul>
          </div>
        </div>
      </section>
    </div>
  `;

  // Scoped DOM query helper
  const $ = (id) => container.querySelector(`#${id}`);

  function showAlert(id, message) {
    const el = $(id);
    if (!el) return;
    el.textContent = message;
    el.classList.remove("hidden");
  }

  function hideAlert(id) {
    const el = $(id);
    if (!el) return;
    el.textContent = "";
    el.classList.add("hidden");
  }

  function setMode(mode) {
    state.mode = mode;
    container.querySelectorAll(".mode-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === mode);
    });
    $("hide-panel").classList.toggle("hidden", mode !== "hide");
    $("extract-panel").classList.toggle("hidden", mode !== "extract");
  }

  function setStage(stageNum) {
    state.stage = stageNum;
    const panels = { 1: "stage-1", 2: "stage-2", 3: "stage-3", 4: "stage-result" };
    Object.entries(panels).forEach(([num, id]) => {
      $(id).classList.toggle("active", Number(num) === stageNum);
    });

    const stepper = $("stepper");
    stepper.classList.toggle("hidden", stageNum === 4);
    stepper.querySelectorAll(".stepper-item").forEach((item) => {
      const s = Number(item.dataset.stage);
      item.classList.toggle("active", s === stageNum);
      item.classList.toggle("completed", s < stageNum);
    });

    if (stageNum === 3) {
      populateStage3Summary();
      refreshCapacityAnalysis();
    }
  }

  // --- Load File Categories dynamically from Backend ---
  const categoryGrid = $("category-grid");
  const payloadUploadSection = $("payload-upload-section");
  const payloadFileInput = $("payload-file-input");

  try {
    const catRes = await fetch(`${API_BASE}/categories`);
    const catData = await catRes.json();
    if (!catRes.ok || !catData.ok) throw new Error(catData.message || "Failed to load categories.");

    categoryGrid.innerHTML = catData.categories
      .map((cat) => {
        const extText = cat.extensions.includes("*")
          ? "Any Extension"
          : cat.extensions.map((e) => e.toUpperCase()).join(" · ");
        return `
          <button
            type="button"
            class="category-card"
            data-category="${escapeHtml(cat.id)}"
            data-extensions="${escapeHtml(cat.extensions.join(","))}"
          >
            <div class="category-title">${escapeHtml(cat.label)}</div>
            <div class="category-exts">${escapeHtml(extText)}</div>
          </button>
        `;
      })
      .join("");

    categoryGrid.querySelectorAll(".category-card").forEach((card) => {
      card.addEventListener("click", () => {
        const catId = card.dataset.category;
        const exts = (card.dataset.extensions || "").split(",").filter(Boolean);
        const isCategoryChanged = state.selectedCategory && state.selectedCategory !== catId;

        state.selectedCategory = catId;
        state.allowedExtensions = exts;

        categoryGrid.querySelectorAll(".category-card").forEach((c) => {
          c.classList.toggle("selected", c === card);
        });

        const label = card.querySelector(".category-title").textContent;
        $("selected-category-title").textContent = `Upload ${label}`;
        if (exts.includes("*")) {
          $("selected-category-hint").textContent = "All file extensions are accepted.";
          $("payload-accept-hint").textContent = "Select one or multiple files of any type.";
          payloadFileInput.removeAttribute("accept");
        } else {
          const displayExts = exts.map((e) => `.${e.toUpperCase()}`).join(", ");
          $("selected-category-hint").textContent = `Allowed extensions: ${displayExts}`;
          $("payload-accept-hint").textContent = `Accepted formats: ${displayExts}`;
          payloadFileInput.setAttribute("accept", exts.map((e) => `.${e}`).join(","));
        }

        if (isCategoryChanged) {
          state.payloadFiles = [];
          renderSelectedFiles();
        }
        hideAlert("stage2-error");
        payloadUploadSection.classList.remove("hidden");
      });
    });
  } catch (err) {
    categoryGrid.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message || "Could not load file categories.")}</div>`;
  }

  // --- Stage 1: Container Image ---
  const imageDropzone = $("image-dropzone");
  const imageFileInput = $("image-file-input");
  const browseImageBtn = $("browse-image-btn");
  const changeImageBtn = $("change-image-btn");
  const stage1ContinueBtn = $("stage1-continue-btn");

  async function handleContainerImageSelected(file) {
    hideAlert("stage1-error");
    if (!file) return;

    const ext = getExtension(file.name);
    if (!["png", "jpg", "jpeg"].includes(ext)) {
      showAlert("stage1-error", "Unsupported image format. Please select a PNG or JPEG/JPG image.");
      return;
    }

    const formData = new FormData();
    formData.append("image", file);

    try {
      const res = await fetch(`${API_BASE}/analyze-image`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert("stage1-error", data.message || "Unable to validate image.");
        return;
      }

      if (state.containerPreviewUrl) URL.revokeObjectURL(state.containerPreviewUrl);
      state.containerFile = file;
      state.containerInfo = data.image;
      state.containerPreviewUrl = URL.createObjectURL(file);

      $("container-preview-img").src = state.containerPreviewUrl;
      $("img-meta-name").textContent = data.image.filename;
      $("img-meta-dims").textContent = data.image.dimensions;
      $("img-meta-size").textContent = data.image.original_size_formatted;
      $("img-meta-capacity").textContent = formatAllUnits(data.image.capacity);
      $("jpeg-notice").classList.toggle("hidden", !data.image.converted_from_jpeg);

      imageDropzone.classList.add("hidden");
      $("image-preview-panel").classList.remove("hidden");
      stage1ContinueBtn.disabled = false;
    } catch (_err) {
      showAlert("stage1-error", "Network error while analyzing the image. Please try again.");
    }
  }

  browseImageBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    imageFileInput.click();
  });
  imageDropzone.addEventListener("click", () => imageFileInput.click());
  imageDropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") imageFileInput.click();
  });
  imageFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleContainerImageSelected(e.target.files[0]);
  });
  ["dragover", "dragenter"].forEach((evt) => {
    imageDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      imageDropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    imageDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      imageDropzone.classList.remove("dragover");
    });
  });
  imageDropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleContainerImageSelected(file);
  });
  changeImageBtn.addEventListener("click", () => {
    imageFileInput.value = "";
    imageFileInput.click();
  });
  stage1ContinueBtn.addEventListener("click", () => {
    if (!state.containerFile || !state.containerInfo) return;
    setStage(2);
  });

  // --- Stage 2: Payload Files ---
  const payloadDropzone = $("payload-dropzone");
  const addMoreFilesBtn = $("add-more-files-btn");
  const stage2ContinueBtn = $("stage2-continue-btn");

  function renderSelectedFiles() {
    const listWrap = $("selected-files-container");
    const listEl = $("selected-files-list");
    listEl.innerHTML = "";

    if (state.payloadFiles.length === 0) {
      listWrap.classList.add("hidden");
      stage2ContinueBtn.disabled = true;
      return;
    }

    let totalBytes = 0;
    state.payloadFiles.forEach((file, index) => {
      totalBytes += file.size;
      const ext = getExtension(file.name) || "FILE";
      const li = document.createElement("li");
      li.className = "file-item";
      li.innerHTML = `
        <div class="file-item-info">
          <span class="file-ext-badge mono">${escapeHtml(ext)}</span>
          <span class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
        </div>
        <div class="file-item-meta">
          <span class="mono">${formatBytes(file.size)}</span>
          <button type="button" class="btn-danger-ghost" data-remove-index="${index}">Remove</button>
        </div>
      `;
      listEl.appendChild(li);
    });

    listEl.querySelectorAll("[data-remove-index]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.payloadFiles.splice(Number(btn.dataset.removeIndex), 1);
        renderSelectedFiles();
      });
    });

    $("selected-files-count").textContent =
      state.payloadFiles.length === 1 ? "1 file selected" : `${state.payloadFiles.length} files selected`;
    $("selected-files-total-size").textContent = `Total: ${formatBytes(totalBytes)}`;
    listWrap.classList.remove("hidden");
    stage2ContinueBtn.disabled = false;
  }

  function addPayloadFiles(fileList) {
    hideAlert("stage2-error");
    if (!state.selectedCategory) {
      showAlert("stage2-error", "Please select a file category first.");
      return;
    }
    const rejected = [];
    for (const file of Array.from(fileList)) {
      const ext = getExtension(file.name);
      if (!state.allowedExtensions.includes("*") && (!ext || !state.allowedExtensions.includes(ext))) {
        rejected.push(file.name);
        continue;
      }
      state.payloadFiles.push(file);
    }
    if (rejected.length > 0) {
      const allowedText = state.allowedExtensions.map((e) => `.${e.toUpperCase()}`).join(", ");
      showAlert(
        "stage2-error",
        `Skipped unsupported file(s): ${rejected.join(", ")}. Allowed for this category: ${allowedText}.`
      );
    }
    renderSelectedFiles();
  }

  payloadDropzone.addEventListener("click", () => payloadFileInput.click());
  addMoreFilesBtn.addEventListener("click", () => payloadFileInput.click());
  payloadFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      addPayloadFiles(e.target.files);
      payloadFileInput.value = "";
    }
  });
  ["dragover", "dragenter"].forEach((evt) => {
    payloadDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      payloadDropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    payloadDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      payloadDropzone.classList.remove("dragover");
    });
  });
  payloadDropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addPayloadFiles(e.dataTransfer.files);
    }
  });
  $("stage2-back-btn").addEventListener("click", () => setStage(1));
  stage2ContinueBtn.addEventListener("click", () => {
    if (state.payloadFiles.length === 0) {
      showAlert("stage2-error", "Please select at least one file to hide.");
      return;
    }
    setStage(3);
  });

  // --- Stage 3: Summary, Storage Analysis, Encryption & Encoding ---
  const encryptionToggle = $("enable-encryption-toggle");
  const passwordFields = $("password-fields");
  const encodePasswordInput = $("encode-password");
  const encodePasswordConfirm = $("encode-password-confirm");
  const generateBtn = $("generate-btn");

  function populateStage3Summary() {
    $("sum-img-name").textContent = state.containerInfo.filename;
    $("sum-img-dims").textContent = state.containerInfo.dimensions;
    $("sum-img-size").textContent = state.containerInfo.original_size_formatted;

    const totalSize = state.payloadFiles.reduce((acc, f) => acc + f.size, 0);
    $("sum-file-count").textContent = `${state.payloadFiles.length}`;
    $("sum-file-total").textContent = formatBytes(totalSize);

    const namesUl = $("sum-file-names");
    namesUl.innerHTML = "";
    state.payloadFiles.forEach((f) => {
      const li = document.createElement("li");
      li.textContent = `• ${f.name} (${formatBytes(f.size)})`;
      namesUl.appendChild(li);
    });
  }

  async function refreshCapacityAnalysis() {
    hideAlert("stage3-error");
    generateBtn.disabled = true;

    const badge = $("storage-status-badge");
    badge.textContent = "Calculating...";
    badge.className = "badge badge-info";

    const formData = new FormData();
    formData.append("image", state.containerFile);
    formData.append("category", state.selectedCategory);
    formData.append("use_encryption", encryptionToggle.checked ? "true" : "false");
    state.payloadFiles.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch(`${API_BASE}/analyze-capacity`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert("stage3-error", data.message || "Failed to analyze storage capacity.");
        badge.textContent = "Error";
        badge.className = "badge badge-danger";
        return;
      }

      const storage = data.storage;
      state.storageAnalysis = storage;

      $("cap-available").textContent = formatAllUnits(storage.available);
      $("cap-required").textContent = formatAllUnits(storage.required);
      $("cap-remaining").textContent = storage.fits
        ? formatAllUnits(storage.remaining)
        : `Exceeded by ${formatBytes(storage.overflow_bytes)}`;

      const barFill = $("capacity-bar-fill");
      barFill.style.width = `${Math.min(100, storage.utilization_percent)}%`;
      barFill.classList.toggle("over", !storage.fits);

      if (storage.fits) {
        badge.textContent = `Ready (${storage.utilization_percent}% used)`;
        badge.className = "badge badge-success";
        generateBtn.disabled = false;
      } else {
        badge.textContent = "Capacity Exceeded";
        badge.className = "badge badge-danger";
        showAlert(
          "stage3-error",
          `Selected files require ${formatBytes(storage.required_bytes)}, which exceeds the image's available capacity of ${formatBytes(storage.available_bytes)}. Please use a larger image or fewer/smaller files.`
        );
        generateBtn.disabled = true;
      }
    } catch (_err) {
      showAlert("stage3-error", "Network error while checking image capacity.");
    }
  }

  encryptionToggle.addEventListener("change", () => {
    passwordFields.classList.toggle("hidden", !encryptionToggle.checked);
    refreshCapacityAnalysis();
  });

  $("stage3-back-btn").addEventListener("click", () => {
    $("encoding-progress-panel").classList.add("hidden");
    setStage(2);
  });

  function setProgressStep(activeStep) {
    container.querySelectorAll("#encoding-steps-list li").forEach((li) => {
      const step = Number(li.dataset.step);
      li.classList.toggle("done", step < activeStep);
      li.classList.toggle("active", step === activeStep);
    });
  }

  generateBtn.addEventListener("click", async () => {
    hideAlert("stage3-error");
    if (!state.storageAnalysis || !state.storageAnalysis.fits) {
      showAlert("stage3-error", "Cannot encode because the payload exceeds available image capacity.");
      return;
    }

    if (encryptionToggle.checked) {
      const pwd = encodePasswordInput.value;
      const confirmPwd = encodePasswordConfirm.value;
      if (!pwd) {
        showAlert("stage3-error", "Please enter a password to enable encryption.");
        return;
      }
      if (pwd !== confirmPwd) {
        showAlert("stage3-error", "Passwords do not match. Please re-enter your password.");
        return;
      }
    }

    generateBtn.disabled = true;
    const progressPanel = $("encoding-progress-panel");
    progressPanel.classList.remove("hidden");

    let currentStep = 1;
    setProgressStep(currentStep);
    const timer = setInterval(() => {
      if (currentStep < 5) {
        currentStep += 1;
        setProgressStep(currentStep);
      }
    }, 220);

    const formData = new FormData();
    formData.append("image", state.containerFile);
    formData.append("category", state.selectedCategory);
    formData.append("use_encryption", encryptionToggle.checked ? "true" : "false");
    if (encryptionToggle.checked) {
      formData.append("password", encodePasswordInput.value);
    }
    state.payloadFiles.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch(`${API_BASE}/encode`, { method: "POST", body: formData });
      const data = await res.json();
      clearInterval(timer);

      if (!res.ok || !data.ok) {
        progressPanel.classList.add("hidden");
        showAlert("stage3-error", data.message || "Encoding failed. Please verify your inputs.");
        generateBtn.disabled = false;
        return;
      }

      setProgressStep(7);

      $("result-original-img").src = state.containerPreviewUrl;
      $("result-encoded-img").src = data.encoded_preview_data_url;
      $("res-orig-size").textContent = data.original_image.original_size_formatted;
      $("res-enc-size").textContent = data.encoded_size_formatted;
      $("res-file-count").textContent = `${data.file_count}`;
      $("res-data-size").textContent = `${data.raw_files_size_formatted} (${data.embedded_payload_formatted} embedded)`;
      $("res-algorithm").textContent = data.algorithm;

      const dlBtn = $("download-encoded-btn");
      dlBtn.href = data.download_url;
      dlBtn.setAttribute("download", data.download_filename);

      setTimeout(() => {
        progressPanel.classList.add("hidden");
        setStage(4);
      }, 220);
    } catch (_err) {
      clearInterval(timer);
      progressPanel.classList.add("hidden");
      showAlert("stage3-error", "Network error during encoding. Please try again.");
      generateBtn.disabled = false;
    }
  });

  $("start-new-btn").addEventListener("click", () => {
    if (state.containerPreviewUrl) URL.revokeObjectURL(state.containerPreviewUrl);
    state.containerFile = null;
    state.containerPreviewUrl = null;
    state.containerInfo = null;
    state.selectedCategory = null;
    state.allowedExtensions = [];
    state.payloadFiles = [];
    state.storageAnalysis = null;

    imageFileInput.value = "";
    payloadFileInput.value = "";
    encodePasswordInput.value = "";
    encodePasswordConfirm.value = "";
    encryptionToggle.checked = false;
    passwordFields.classList.add("hidden");

    imageDropzone.classList.remove("hidden");
    $("image-preview-panel").classList.add("hidden");
    stage1ContinueBtn.disabled = true;

    categoryGrid.querySelectorAll(".category-card").forEach((c) => c.classList.remove("selected"));
    payloadUploadSection.classList.add("hidden");
    renderSelectedFiles();

    hideAlert("stage1-error");
    hideAlert("stage2-error");
    hideAlert("stage3-error");
    setStage(1);
  });

  // --- Extract Files Section ---
  const extractDropzone = $("extract-dropzone");
  const extractFileInput = $("extract-file-input");
  const browseExtractBtn = $("browse-extract-btn");
  const runExtractBtn = $("run-extract-btn");
  const resetExtractBtn = $("reset-extract-btn");
  const extractPasswordInput = $("extract-password");

  function resetExtractSection() {
    if (state.extractPreviewUrl) URL.revokeObjectURL(state.extractPreviewUrl);
    state.extractFile = null;
    state.extractPreviewUrl = null;
    state.extractInspection = null;
    state.extractInspectToken = null;
    extractFileInput.value = "";
    extractPasswordInput.value = "";
    hideAlert("extract-error");
    hideAlert("extract-info");
    extractDropzone.classList.remove("hidden");
    $("extract-inspect-panel").classList.add("hidden");
    $("extract-results-panel").classList.add("hidden");
  }

  async function handleExtractImageSelected(file) {
    hideAlert("extract-error");
    hideAlert("extract-info");
    $("extract-results-panel").classList.add("hidden");

    if (!file) return;
    if (getExtension(file.name) !== "png") {
      showAlert("extract-error", "Encoded images must be lossless PNG files.");
      return;
    }

    const formData = new FormData();
    formData.append("image", file);

    try {
      const res = await fetch(`${API_BASE}/inspect`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert("extract-error", data.message || "Could not inspect the uploaded PNG image.");
        return;
      }

      if (state.extractPreviewUrl) URL.revokeObjectURL(state.extractPreviewUrl);
      state.extractFile = file;
      state.extractPreviewUrl = URL.createObjectURL(file);
      state.extractInspection = data;
      state.extractInspectToken = data.inspect_token || null;

      $("extract-preview-img").src = state.extractPreviewUrl;
      $("ext-meta-name").textContent = data.image.filename;
      $("ext-meta-dims").textContent = data.image.dimensions;

      extractDropzone.classList.add("hidden");
      $("extract-inspect-panel").classList.remove("hidden");

      const statusEl = $("ext-meta-status");
      const pwdWrap = $("extract-password-wrap");

      if (!data.has_payload) {
        statusEl.textContent = "Not Detected";
        statusEl.className = "detail-value badge badge-danger";
        pwdWrap.classList.add("hidden");
        runExtractBtn.disabled = true;
        showAlert("extract-error", data.message || "No hidden data from this application was detected.");
        return;
      }

      const isEncrypted = Boolean(data.metadata && data.metadata.is_encrypted);
      statusEl.textContent = isEncrypted ? "Encrypted Payload Detected" : "Payload Detected";
      statusEl.className = "detail-value badge badge-success";
      pwdWrap.classList.toggle("hidden", !isEncrypted);
      runExtractBtn.disabled = false;
      showAlert("extract-info", data.message);
    } catch (_err) {
      showAlert("extract-error", "Network error while inspecting the PNG image.");
    }
  }

  browseExtractBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    extractFileInput.click();
  });
  extractDropzone.addEventListener("click", () => extractFileInput.click());
  extractFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleExtractImageSelected(e.target.files[0]);
  });
  ["dragover", "dragenter"].forEach((evt) => {
    extractDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      extractDropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    extractDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      extractDropzone.classList.remove("dragover");
    });
  });
  extractDropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleExtractImageSelected(file);
  });
  resetExtractBtn.addEventListener("click", resetExtractSection);

  runExtractBtn.addEventListener("click", async () => {
    hideAlert("extract-error");
    if (!state.extractFile) return;

    const isEncrypted = Boolean(
      state.extractInspection &&
      state.extractInspection.metadata &&
      state.extractInspection.metadata.is_encrypted
    );
    if (isEncrypted && !extractPasswordInput.value) {
      showAlert("extract-error", "Please enter the password to decrypt the hidden files.");
      return;
    }

    runExtractBtn.disabled = true;
    runExtractBtn.textContent = "Extracting...";
    const formData = new FormData();
    if (state.extractInspectToken) {
      formData.append("inspect_token", state.extractInspectToken);
    } else {
      formData.append("image", state.extractFile);
    }
    if (extractPasswordInput.value) {
      formData.append("password", extractPasswordInput.value);
    }

    try {
      const res = await fetch(`${API_BASE}/extract`, { method: "POST", body: formData });
      const data = await res.json();
      runExtractBtn.disabled = false;
      runExtractBtn.textContent = "Extract Files";

      if (!res.ok || !data.ok) {
        showAlert("extract-error", data.message || "Extraction failed.");
        return;
      }

      const listEl = $("extracted-files-list");
      listEl.innerHTML = "";
      data.files.forEach((f) => {
        const li = document.createElement("li");
        li.className = "file-item";
        li.innerHTML = `
          <div class="file-item-info">
            <span class="file-ext-badge mono">${escapeHtml(f.extension || "FILE")}</span>
            <span class="file-name" title="${escapeHtml(f.filename)}">${escapeHtml(f.filename)}</span>
          </div>
          <div class="file-item-meta">
            <span class="mono">${escapeHtml(f.size_formatted)}</span>
            <a href="${escapeHtml(f.download_url)}" download="${escapeHtml(f.filename)}" class="btn btn-secondary btn-sm">Download</a>
          </div>
        `;
        listEl.appendChild(li);
      });

      $("extract-results-meta").textContent = `${data.file_count} file(s) recovered · Total ${data.total_size_formatted}`;

      const zipBtn = $("download-all-zip-btn");
      if (data.zip_download_url) {
        zipBtn.href = data.zip_download_url;
        zipBtn.classList.remove("hidden");
      } else {
        zipBtn.classList.add("hidden");
      }

      $("extract-results-panel").classList.remove("hidden");
    } catch (_err) {
      runExtractBtn.disabled = false;
      runExtractBtn.textContent = "Extract Files";
      showAlert("extract-error", "Network error during extraction. Please try again.");
    }
  });

  $("nav-hide-btn").addEventListener("click", () => setMode("hide"));
  $("nav-extract-btn").addEventListener("click", () => setMode("extract"));

  setMode("hide");
  setStage(1);

  return () => {
    if (state.containerPreviewUrl) URL.revokeObjectURL(state.containerPreviewUrl);
    if (state.extractPreviewUrl) URL.revokeObjectURL(state.extractPreviewUrl);
  };
}
