/**
 * CITADEL Full-Screen Opening Sequence Overlay
 * Integrates citadel_opening_intro.html directly into the CITADEL SPA.
 * Automatically hands off to CITADEL's main interface and starts theme music.
 */

class CitadelIntroAudioEngine {
  constructor() {
    this.ctx = null;
    this.masterGain = null;
    this.sequenceGain = null;
    this.activeNodes = [];
  }

  init() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return false;
      if (!this.ctx || this.ctx.state === "closed") {
        this.ctx = new AudioCtx();
      }
      if (this.ctx.state === "suspended") {
        this.ctx.resume();
      }
      if (!this.masterGain) {
        this.masterGain = this.ctx.createGain();
        this.masterGain.gain.setValueAtTime(0.8, this.ctx.currentTime);
        this.masterGain.connect(this.ctx.destination);
      }
      return true;
    } catch (_err) {
      return false;
    }
  }

  resetSequenceBus() {
    if (!this.ctx || !this.masterGain) return null;
    if (this.sequenceGain) {
      try {
        this.sequenceGain.disconnect();
      } catch (_err) {
        // ignore
      }
    }
    this.sequenceGain = this.ctx.createGain();
    this.sequenceGain.gain.setValueAtTime(1.0, this.ctx.currentTime);
    this.sequenceGain.connect(this.masterGain);
    return this.sequenceGain;
  }

  createWhiteNoiseBuffer(durationSec) {
    const length = Math.max(1, Math.floor(this.ctx.sampleRate * durationSec));
    const buffer = this.ctx.createBuffer(1, length, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i++) {
      data[i] = Math.random() * 2 - 1;
    }
    return buffer;
  }

  playIntroSequence() {
    if (!this.init() || !this.ctx || !this.masterGain) return;
    this.stopSequence();
    const bus = this.resetSequenceBus();
    if (!bus) return;

    const now = this.ctx.currentTime;

    // Phase 1 (0.0s - 1.2s): Dark ambient drone
    const droneFilter = this.ctx.createBiquadFilter();
    droneFilter.type = "lowpass";
    droneFilter.Q.setValueAtTime(2.4, now);
    droneFilter.frequency.setValueAtTime(85, now);
    droneFilter.frequency.exponentialRampToValueAtTime(460, now + 1.35);
    droneFilter.frequency.exponentialRampToValueAtTime(140, now + 2.0);

    const droneGain = this.ctx.createGain();
    droneGain.gain.setValueAtTime(0.0001, now);
    droneGain.gain.exponentialRampToValueAtTime(0.26, now + 1.15);
    droneGain.gain.linearRampToValueAtTime(0.22, now + 1.75);
    droneGain.gain.exponentialRampToValueAtTime(0.0001, now + 2.15);

    droneFilter.connect(droneGain);
    droneGain.connect(bus);

    [
      { type: "sawtooth", freq: 55.0, detune: -7 },
      { type: "sawtooth", freq: 55.0, detune: 7 },
      { type: "sine", freq: 55.0, detune: 0 },
      { type: "triangle", freq: 82.41, detune: 2 },
    ].forEach(({ type, freq, detune }) => {
      const osc = this.ctx.createOscillator();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, now);
      osc.detune.setValueAtTime(detune, now);
      osc.connect(droneFilter);
      osc.start(now);
      osc.stop(now + 2.2);
      this.activeNodes.push(osc);
    });

    // Phase 2 (1.2s - 2.2s): Filtered noise whoosh + riser
    const whooshStart = now + 1.15;
    const whooshDur = 1.05;
    const noiseSrc = this.ctx.createBufferSource();
    noiseSrc.buffer = this.createWhiteNoiseBuffer(whooshDur);

    const whooshFilter = this.ctx.createBiquadFilter();
    whooshFilter.type = "bandpass";
    whooshFilter.Q.setValueAtTime(1.6, whooshStart);
    whooshFilter.Q.exponentialRampToValueAtTime(6.2, whooshStart + 0.82);
    whooshFilter.Q.exponentialRampToValueAtTime(1.5, whooshStart + whooshDur);
    whooshFilter.frequency.setValueAtTime(140, whooshStart);
    whooshFilter.frequency.exponentialRampToValueAtTime(3600, whooshStart + 0.82);
    whooshFilter.frequency.exponentialRampToValueAtTime(240, whooshStart + whooshDur);

    const whooshGain = this.ctx.createGain();
    whooshGain.gain.setValueAtTime(0.0001, whooshStart);
    whooshGain.gain.exponentialRampToValueAtTime(0.42, whooshStart + 0.78);
    whooshGain.gain.exponentialRampToValueAtTime(0.0001, whooshStart + whooshDur);

    noiseSrc.connect(whooshFilter);
    whooshFilter.connect(whooshGain);
    whooshGain.connect(bus);
    noiseSrc.start(whooshStart);
    noiseSrc.stop(whooshStart + whooshDur + 0.02);
    this.activeNodes.push(noiseSrc);

    const riserOsc = this.ctx.createOscillator();
    const riserFilter = this.ctx.createBiquadFilter();
    const riserGain = this.ctx.createGain();
    riserOsc.type = "sawtooth";
    riserOsc.frequency.setValueAtTime(75, whooshStart);
    riserOsc.frequency.exponentialRampToValueAtTime(260, whooshStart + 0.83);
    riserFilter.type = "lowpass";
    riserFilter.frequency.setValueAtTime(240, whooshStart);
    riserFilter.frequency.exponentialRampToValueAtTime(1400, whooshStart + 0.83);
    riserGain.gain.setValueAtTime(0.0001, whooshStart);
    riserGain.gain.exponentialRampToValueAtTime(0.14, whooshStart + 0.78);
    riserGain.gain.exponentialRampToValueAtTime(0.0001, whooshStart + 0.88);
    riserOsc.connect(riserFilter);
    riserFilter.connect(riserGain);
    riserGain.connect(bus);
    riserOsc.start(whooshStart);
    riserOsc.stop(whooshStart + 0.9);
    this.activeNodes.push(riserOsc);

    // Phase 3 (2.0s - 3.5s): Sub-bass drop + impact + resonant tail
    const impactTime = now + 1.98;
    const subOsc = this.ctx.createOscillator();
    const subGain = this.ctx.createGain();
    subOsc.type = "sine";
    subOsc.frequency.setValueAtTime(140, impactTime);
    subOsc.frequency.exponentialRampToValueAtTime(42, impactTime + 0.14);
    subOsc.frequency.exponentialRampToValueAtTime(32, impactTime + 0.55);
    subOsc.frequency.exponentialRampToValueAtTime(28, impactTime + 1.48);
    subGain.gain.setValueAtTime(0.0001, impactTime);
    subGain.gain.linearRampToValueAtTime(0.85, impactTime + 0.01);
    subGain.gain.exponentialRampToValueAtTime(0.32, impactTime + 0.45);
    subGain.gain.exponentialRampToValueAtTime(0.0001, impactTime + 1.52);
    subOsc.connect(subGain);
    subGain.connect(bus);
    subOsc.start(impactTime);
    subOsc.stop(impactTime + 1.55);
    this.activeNodes.push(subOsc);

    const punchOsc = this.ctx.createOscillator();
    const punchFilter = this.ctx.createBiquadFilter();
    const punchGain = this.ctx.createGain();
    punchOsc.type = "triangle";
    punchOsc.frequency.setValueAtTime(180, impactTime);
    punchOsc.frequency.exponentialRampToValueAtTime(48, impactTime + 0.14);
    punchFilter.type = "lowpass";
    punchFilter.frequency.setValueAtTime(720, impactTime);
    punchFilter.frequency.exponentialRampToValueAtTime(120, impactTime + 0.22);
    punchGain.gain.setValueAtTime(0.0001, impactTime);
    punchGain.gain.linearRampToValueAtTime(0.48, impactTime + 0.006);
    punchGain.gain.exponentialRampToValueAtTime(0.0001, impactTime + 0.24);
    punchOsc.connect(punchFilter);
    punchFilter.connect(punchGain);
    punchGain.connect(bus);
    punchOsc.start(impactTime);
    punchOsc.stop(impactTime + 0.26);
    this.activeNodes.push(punchOsc);

    const slamDur = 0.52;
    const slamSrc = this.ctx.createBufferSource();
    slamSrc.buffer = this.createWhiteNoiseBuffer(slamDur);
    const slamFilter = this.ctx.createBiquadFilter();
    slamFilter.type = "lowpass";
    slamFilter.frequency.setValueAtTime(1600, impactTime);
    slamFilter.frequency.exponentialRampToValueAtTime(140, impactTime + slamDur);
    const slamGain = this.ctx.createGain();
    slamGain.gain.setValueAtTime(0.0001, impactTime);
    slamGain.gain.linearRampToValueAtTime(0.45, impactTime + 0.008);
    slamGain.gain.exponentialRampToValueAtTime(0.0001, impactTime + slamDur);
    slamSrc.connect(slamFilter);
    slamFilter.connect(slamGain);
    slamGain.connect(bus);
    slamSrc.start(impactTime);
    slamSrc.stop(impactTime + slamDur + 0.02);
    this.activeNodes.push(slamSrc);

    const tailFilter = this.ctx.createBiquadFilter();
    tailFilter.type = "lowpass";
    tailFilter.Q.setValueAtTime(3.2, impactTime);
    tailFilter.frequency.setValueAtTime(920, impactTime);
    tailFilter.frequency.exponentialRampToValueAtTime(130, impactTime + 1.5);
    const tailGain = this.ctx.createGain();
    tailGain.gain.setValueAtTime(0.0001, impactTime);
    tailGain.gain.linearRampToValueAtTime(0.24, impactTime + 0.03);
    tailGain.gain.exponentialRampToValueAtTime(0.0001, impactTime + 1.52);
    tailFilter.connect(tailGain);
    tailGain.connect(bus);

    [
      { freq: 65.41, detune: -6 },
      { freq: 65.41, detune: 6 },
      { freq: 98.0, detune: 3 },
    ].forEach(({ freq, detune }) => {
      const osc = this.ctx.createOscillator();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(freq, impactTime);
      osc.detune.setValueAtTime(detune, impactTime);
      osc.connect(tailFilter);
      osc.start(impactTime);
      osc.stop(impactTime + 1.55);
      this.activeNodes.push(osc);
    });
  }

  stopSequence() {
    try {
      if (this.ctx && this.sequenceGain) {
        const now = this.ctx.currentTime;
        this.sequenceGain.gain.cancelScheduledValues(now);
        this.sequenceGain.gain.setValueAtTime(this.sequenceGain.gain.value, now);
        this.sequenceGain.gain.linearRampToValueAtTime(0.0001, now + 0.04);
      }
      this.activeNodes.forEach((node) => {
        try {
          node.stop();
        } catch (_err) {
          // ignore
        }
      });
      this.activeNodes = [];
    } catch (_err) {
      // ignore
    }
  }
}

export function initIntroOverlay({ onComplete } = {}) {
  const existing = document.getElementById("citadel-intro-overlay");
  if (existing) existing.remove();

  const overlay = document.createElement("div");
  overlay.id = "citadel-intro-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "CITADEL Intro Sequence");

  overlay.innerHTML = `
    <div class="intro-vignette"></div>
    <div id="intro-impact-flash"></div>

    <div class="intro-corner intro-corner-tl"></div>
    <div class="intro-corner intro-corner-tr"></div>
    <div class="intro-corner intro-corner-bl"></div>
    <div class="intro-corner intro-corner-br"></div>

    <button id="skip-intro-btn" type="button" aria-label="Skip Intro">
      Skip Intro &rarr;
    </button>

    <div id="intro-init-prompt" tabindex="0" role="button" aria-label="Initialize and Enter CITADEL">
      <div class="intro-prompt-inner">
        <div class="pulse-ring">
          <div class="pulse-dot"></div>
        </div>
        <div>
          <p class="intro-prompt-title">INITIALIZE // CLICK TO ENTER</p>
          <p class="intro-prompt-sub">AUDIO ENABLED &bull; PRESS ANY KEY OR CLICK</p>
        </div>
      </div>
    </div>

    <div id="intro-stage">
      <div id="intro-emblem-wrap">
        <img
          id="intro-emblem-img"
          src="/assets/logos/citadel_intrologo.jpeg"
          alt="Citadel Emblem"
          class="citadel-jpeg-blend"
        />
        <svg id="emblem-fallback-svg" viewBox="0 0 300 320" class="hidden" xmlns="http://www.w3.org/2000/svg" aria-label="Citadel Emblem Fallback">
          <path d="M174 14 C146 38 142 66 154 88 C126 70 112 46 112 46 C76 74 72 114 82 138 C56 128 42 104 42 104 C12 146 22 198 54 226 L60 282 L146 312 L232 280 L238 220 C276 190 294 140 256 88 C258 118 242 140 218 144 C232 108 224 68 186 42 C176 32 172 22 174 14 Z" fill="#e5e7eb" />
          <path d="M148 126 C112 128 92 154 92 186 L92 232 C92 242 100 248 108 250 L108 272 C116 276 124 278 131 278 L134 256 L142 256 L142 280 C148 280 155 280 162 278 L164 256 L172 256 L174 274 C182 270 189 266 194 260 L194 246 C202 242 208 236 208 226 L206 184 C206 150 184 126 148 126 Z" fill="#f9fafb" />
          <polygon points="116,164 134,228 110,224" fill="#050505" />
          <polygon points="180,164 162,228 186,224" fill="#050505" />
        </svg>
      </div>

      <div id="intro-title-wrap">
        <img
          id="intro-title-img"
          src="/assets/logos/citadel_logo.jpeg"
          alt="CITADEL"
          class="citadel-jpeg-blend"
        />
        <svg id="title-fallback-svg" viewBox="0 0 920 200" class="hidden" xmlns="http://www.w3.org/2000/svg" aria-label="CITADEL Title Fallback">
          <text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" fill="#f9fafb" font-family="'Inter', Impact, sans-serif" font-weight="900" font-size="148" letter-spacing="14">CITADEL</text>
        </svg>
        <p id="intro-tagline">SYSTEM ONLINE</p>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  const initPromptEl = overlay.querySelector("#intro-init-prompt");
  const skipBtnEl = overlay.querySelector("#skip-intro-btn");
  const stageEl = overlay.querySelector("#intro-stage");
  const emblemWrapEl = overlay.querySelector("#intro-emblem-wrap");
  const titleWrapEl = overlay.querySelector("#intro-title-wrap");
  const impactFlashEl = overlay.querySelector("#intro-impact-flash");
  const emblemImg = overlay.querySelector("#intro-emblem-img");
  const titleImg = overlay.querySelector("#intro-title-img");

  emblemImg.addEventListener("error", () => {
    emblemImg.style.display = "none";
    overlay.querySelector("#emblem-fallback-svg").classList.remove("hidden");
  });
  titleImg.addEventListener("error", () => {
    titleImg.style.display = "none";
    overlay.querySelector("#title-fallback-svg").classList.remove("hidden");
  });

  const audioEngine = new CitadelIntroAudioEngine();
  let timers = [];
  let isRunning = false;
  let completed = false;

  function clearTimers() {
    timers.forEach((id) => clearTimeout(id));
    timers = [];
  }

  function handoff() {
    if (completed) return;
    completed = true;
    clearTimers();
    isRunning = false;
    window.removeEventListener("keydown", onKeyDown);

    if (typeof onComplete === "function") {
      onComplete();
    }
  }

  function finishIntro() {
    clearTimers();
    isRunning = false;
    overlay.classList.add("intro-fade-out");
    handoff();
    setTimeout(() => {
      overlay.style.display = "none";
      overlay.setAttribute("aria-hidden", "true");
    }, 650);
  }

  function skipIntro(e) {
    if (e) e.stopPropagation();
    clearTimers();
    isRunning = false;
    audioEngine.stopSequence();
    overlay.classList.add("intro-fade-out");
    overlay.style.display = "none";
    overlay.setAttribute("aria-hidden", "true");
    handoff();
  }

  function runSequence() {
    if (isRunning || completed) return;
    isRunning = true;
    initPromptEl.classList.add("hidden-prompt");
    audioEngine.playIntroSequence();

    emblemWrapEl.classList.remove("phase-1-appear", "phase-2-zoom");
    void emblemWrapEl.offsetWidth;
    emblemWrapEl.classList.add("phase-1-appear");

    timers.push(
      setTimeout(() => {
        emblemWrapEl.classList.remove("phase-1-appear");
        emblemWrapEl.classList.add("phase-2-zoom");
      }, 1200)
    );

    timers.push(
      setTimeout(() => {
        titleWrapEl.classList.remove("phase-3-reveal");
        impactFlashEl.classList.remove("flash-active");
        stageEl.classList.remove("stage-shake");
        void titleWrapEl.offsetWidth;
        titleWrapEl.classList.add("phase-3-reveal");
        impactFlashEl.classList.add("flash-active");
        stageEl.classList.add("stage-shake");
      }, 2000)
    );

    timers.push(
      setTimeout(() => {
        finishIntro();
      }, 3500)
    );
  }

  function onKeyDown(e) {
    if (overlay.style.display === "none") return;
    if (e.key === "Escape") {
      skipIntro(e);
    } else if (!isRunning && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      runSequence();
    }
  }

  initPromptEl.addEventListener("click", runSequence);
  skipBtnEl.addEventListener("click", skipIntro);
  window.addEventListener("keydown", onKeyDown);
}
