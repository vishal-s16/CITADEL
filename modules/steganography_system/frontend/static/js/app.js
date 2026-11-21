(() => {
  "use strict";

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
  };

  // --- Utility Helpers ---
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

  function showAlert(id, message) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = message;
    el.classList.remove("hidden");
  }

  function hideAlert(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = "";
    el.classList.add("hidden");
  }

  function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === mode);
    });
    document.getElementById("hide-panel").classList.toggle("hidden", mode !== "hide");
    document.getElementById("extract-panel").classList.toggle("hidden", mode !== "extract");
  }

  function setStage(stageNum) {
    state.stage = stageNum;
    const panels = {
      1: "stage-1",
      2: "stage-2",
      3: "stage-3",
      4: "stage-result",
    };
    Object.entries(panels).forEach(([num, id]) => {
      document.getElementById(id).classList.toggle("active", Number(num) === stageNum);
    });

    const stepper = document.getElementById("stepper");
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

  // --- Stage 1: Container Image ---
  const imageDropzone = document.getElementById("image-dropzone");
  const imageFileInput = document.getElementById("image-file-input");
  const browseImageBtn = document.getElementById("browse-image-btn");
  const changeImageBtn = document.getElementById("change-image-btn");
  const stage1ContinueBtn = document.getElementById("stage1-continue-btn");

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
      const res = await fetch("/api/analyze-image", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert("stage1-error", data.message || "Unable to validate image.");
        return;
      }

      if (state.containerPreviewUrl) URL.revokeObjectURL(state.containerPreviewUrl);
      state.containerFile = file;
      state.containerInfo = data.image;
      state.containerPreviewUrl = URL.createObjectURL(file);

      document.getElementById("container-preview-img").src = state.containerPreviewUrl;
      document.getElementById("img-meta-name").textContent = data.image.filename;
      document.getElementById("img-meta-dims").textContent = data.image.dimensions;
      document.getElementById("img-meta-size").textContent = data.image.original_size_formatted;
      document.getElementById("img-meta-capacity").textContent = formatAllUnits(data.image.capacity);
      document.getElementById("jpeg-notice").classList.toggle("hidden", !data.image.converted_from_jpeg);

      imageDropzone.classList.add("hidden");
      document.getElementById("image-preview-panel").classList.remove("hidden");
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
    if (e.target.files && e.target.files[0]) {
      handleContainerImageSelected(e.target.files[0]);
    }
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

  // --- Stage 2: Select File Type & Payload Files ---
  const categoryGrid = document.getElementById("category-grid");
  const payloadUploadSection = document.getElementById("payload-upload-section");
  const payloadDropzone = document.getElementById("payload-dropzone");
  const payloadFileInput = document.getElementById("payload-file-input");
  const addMoreFilesBtn = document.getElementById("add-more-files-btn");
  const stage2ContinueBtn = document.getElementById("stage2-continue-btn");

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
      document.getElementById("selected-category-title").textContent = `Upload ${label}`;
      if (exts.includes("*")) {
        document.getElementById("selected-category-hint").textContent = "All file extensions are accepted.";
        document.getElementById("payload-accept-hint").textContent = "Select one or multiple files of any type.";
        payloadFileInput.removeAttribute("accept");
      } else {
        const displayExts = exts.map((e) => `.${e.toUpperCase()}`).join(", ");
        document.getElementById("selected-category-hint").textContent = `Allowed extensions: ${displayExts}`;
        document.getElementById("payload-accept-hint").textContent = `Accepted formats: ${displayExts}`;
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

  function renderSelectedFiles() {
    const container = document.getElementById("selected-files-container");
    const listEl = document.getElementById("selected-files-list");
    listEl.innerHTML = "";

    if (state.payloadFiles.length === 0) {
      container.classList.add("hidden");
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
          <span class="file-ext-badge">${ext}</span>
          <span class="file-name" title="${file.name}">${file.name}</span>
        </div>
        <div class="file-item-meta">
          <span class="mono">${formatBytes(file.size)}</span>
          <button type="button" class="btn btn-danger-ghost" data-remove-index="${index}">Remove</button>
        </div>
      `;
      listEl.appendChild(li);
    });

    listEl.querySelectorAll("[data-remove-index]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.removeIndex);
        state.payloadFiles.splice(idx, 1);
        renderSelectedFiles();
      });
    });

    const countLabel = state.payloadFiles.length === 1 ? "1 file selected" : `${state.payloadFiles.length} files selected`;
    document.getElementById("selected-files-count").textContent = countLabel;
    document.getElementById("selected-files-total-size").textContent = `Total: ${formatBytes(totalBytes)}`;
    container.classList.remove("hidden");
    stage2ContinueBtn.disabled = false;
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

  document.getElementById("stage2-back-btn").addEventListener("click", () => setStage(1));
  stage2ContinueBtn.addEventListener("click", () => {
    if (state.payloadFiles.length === 0) {
      showAlert("stage2-error", "Please select at least one file to hide.");
      return;
    }
    setStage(3);
  });

  // --- Stage 3: Summary, Storage Analysis, Encryption & Encoding ---
  const encryptionToggle = document.getElementById("enable-encryption-toggle");
  const passwordFields = document.getElementById("password-fields");
  const encodePasswordInput = document.getElementById("encode-password");
  const encodePasswordConfirm = document.getElementById("encode-password-confirm");
  const generateBtn = document.getElementById("generate-btn");

  function populateStage3Summary() {
    document.getElementById("sum-img-name").textContent = state.containerInfo.filename;
    document.getElementById("sum-img-dims").textContent = state.containerInfo.dimensions;
    document.getElementById("sum-img-size").textContent = state.containerInfo.original_size_formatted;

    const totalSize = state.payloadFiles.reduce((acc, f) => acc + f.size, 0);
    document.getElementById("sum-file-count").textContent = `${state.payloadFiles.length}`;
    document.getElementById("sum-file-total").textContent = formatBytes(totalSize);

    const namesUl = document.getElementById("sum-file-names");
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

    const badge = document.getElementById("storage-status-badge");
    badge.textContent = "Calculating...";
    badge.className = "badge badge-info";

    const formData = new FormData();
    formData.append("image", state.containerFile);
    formData.append("category", state.selectedCategory);
    formData.append("use_encryption", encryptionToggle.checked ? "true" : "false");
    state.payloadFiles.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch("/api/analyze-capacity", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert("stage3-error", data.message || "Failed to analyze storage capacity.");
        badge.textContent = "Error";
        badge.className = "badge badge-danger";
        return;
      }

      const storage = data.storage;
      state.storageAnalysis = storage;

      document.getElementById("cap-available").textContent = formatAllUnits(storage.available);
      document.getElementById("cap-required").textContent = formatAllUnits(storage.required);
      document.getElementById("cap-remaining").textContent = storage.fits
        ? formatAllUnits(storage.remaining)
        : `Exceeded by ${formatBytes(storage.overflow_bytes)}`;

      const barFill = document.getElementById("capacity-bar-fill");
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

  document.getElementById("stage3-back-btn").addEventListener("click", () => {
    document.getElementById("encoding-progress-panel").classList.add("hidden");
    setStage(2);
  });

  function setProgressStep(activeStep) {
    const items = document.querySelectorAll("#encoding-steps-list li");
    items.forEach((li) => {
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
    const progressPanel = document.getElementById("encoding-progress-panel");
    progressPanel.classList.remove("hidden");

    // Visual progression through the 6 backend stages
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
      const res = await fetch("/api/encode", { method: "POST", body: formData });
      const data = await res.json();
      clearInterval(timer);

      if (!res.ok || !data.ok) {
        progressPanel.classList.add("hidden");
        showAlert("stage3-error", data.message || "Encoding failed. Please verify your inputs.");
        generateBtn.disabled = false;
        return;
      }

      setProgressStep(7); // Mark all 6 steps done

      // Populate Result Page
      document.getElementById("result-original-img").src = state.containerPreviewUrl;
      document.getElementById("result-encoded-img").src = data.encoded_preview_data_url;
      document.getElementById("res-orig-size").textContent = data.original_image.original_size_formatted;
      document.getElementById("res-enc-size").textContent = data.encoded_size_formatted;
      document.getElementById("res-file-count").textContent = `${data.file_count}`;
      document.getElementById("res-data-size").textContent = `${data.raw_files_size_formatted} (${data.embedded_payload_formatted} embedded)`;
      document.getElementById("res-algorithm").textContent = data.algorithm;

      const dlBtn = document.getElementById("download-encoded-btn");
      dlBtn.href = data.download_url;
      dlBtn.setAttribute("download", data.download_filename);

      setTimeout(() => {
        progressPanel.classList.add("hidden");
        setStage(4);
      }, 250);
    } catch (_err) {
      clearInterval(timer);
      progressPanel.classList.add("hidden");
      showAlert("stage3-error", "Network error during encoding. Please try again.");
      generateBtn.disabled = false;
    }
  });

  document.getElementById("start-new-btn").addEventListener("click", () => {
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
    document.getElementById("image-preview-panel").classList.add("hidden");
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
  const extractDropzone = document.getElementById("extract-dropzone");
  const extractFileInput = document.getElementById("extract-file-input");
  const browseExtractBtn = document.getElementById("browse-extract-btn");
  const runExtractBtn = document.getElementById("run-extract-btn");
  const resetExtractBtn = document.getElementById("reset-extract-btn");
  const extractPasswordInput = document.getElementById("extract-password");

  function resetExtractSection() {
    if (state.extractPreviewUrl) URL.revokeObjectURL(state.extractPreviewUrl);
    state.extractFile = null;
    state.extractPreviewUrl = null;
    state.extractInspection = null;
    extractFileInput.value = "";
    extractPasswordInput.value = "";
    hideAlert("extract-error");
    hideAlert("extract-info");
    extractDropzone.classList.remove("hidden");
    document.getElementById("extract-inspect-panel").classList.add("hidden");
    document.getElementById("extract-results-panel").classList.add("hidden");
  }

  async function handleExtractImageSelected(file) {
    hideAlert("extract-error");
    hideAlert("extract-info");
    document.getElementById("extract-results-panel").classList.add("hidden");

    if (!file) return;
    if (getExtension(file.name) !== "png") {
      showAlert("extract-error", "Encoded images must be lossless PNG files.");
      return;
    }

    const formData = new FormData();
    formData.append("image", file);

    try {
      const res = await fetch("/api/inspect", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert("extract-error", data.message || "Could not inspect the uploaded PNG image.");
        return;
      }

      if (state.extractPreviewUrl) URL.revokeObjectURL(state.extractPreviewUrl);
      state.extractFile = file;
      state.extractPreviewUrl = URL.createObjectURL(file);
      state.extractInspection = data;

      document.getElementById("extract-preview-img").src = state.extractPreviewUrl;
      document.getElementById("ext-meta-name").textContent = data.image.filename;
      document.getElementById("ext-meta-dims").textContent = data.image.dimensions;

      extractDropzone.classList.add("hidden");
      document.getElementById("extract-inspect-panel").classList.remove("hidden");

      const statusEl = document.getElementById("ext-meta-status");
      const pwdWrap = document.getElementById("extract-password-wrap");

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
    if (e.target.files && e.target.files[0]) {
      handleExtractImageSelected(e.target.files[0]);
    }
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
    const formData = new FormData();
    formData.append("image", state.extractFile);
    if (extractPasswordInput.value) {
      formData.append("password", extractPasswordInput.value);
    }

    try {
      const res = await fetch("/api/extract", { method: "POST", body: formData });
      const data = await res.json();
      runExtractBtn.disabled = false;

      if (!res.ok || !data.ok) {
        showAlert("extract-error", data.message || "Extraction failed.");
        return;
      }

      const listEl = document.getElementById("extracted-files-list");
      listEl.innerHTML = "";
      data.files.forEach((f) => {
        const li = document.createElement("li");
        li.className = "file-item";
        li.innerHTML = `
          <div class="file-item-info">
            <span class="file-ext-badge">${f.extension || "FILE"}</span>
            <span class="file-name" title="${f.filename}">${f.filename}</span>
          </div>
          <div class="file-item-meta">
            <span class="mono">${f.size_formatted}</span>
            <a href="${f.download_url}" download="${f.filename}" class="btn btn-secondary btn-sm">Download</a>
          </div>
        `;
        listEl.appendChild(li);
      });

      document.getElementById("extract-results-meta").textContent =
        `${data.file_count} file(s) recovered · Total ${data.total_size_formatted}`;

      const zipBtn = document.getElementById("download-all-zip-btn");
      if (data.zip_download_url) {
        zipBtn.href = data.zip_download_url;
        zipBtn.classList.remove("hidden");
      } else {
        zipBtn.classList.add("hidden");
      }

      document.getElementById("extract-results-panel").classList.remove("hidden");
    } catch (_err) {
      runExtractBtn.disabled = false;
      showAlert("extract-error", "Network error during extraction. Please try again.");
    }
  });

  // --- Navigation ---
  document.getElementById("nav-hide-btn").addEventListener("click", () => setMode("hide"));
  document.getElementById("nav-extract-btn").addEventListener("click", () => setMode("extract"));

  setMode("hide");
  setStage(1);
})();
