/**
 * CITADEL Persistent Background Music Player
 * - Never autoplays before user interaction.
 * - Persists uninterrupted across SPA route transitions.
 * - Supports Play/Pause, Mute/Unmute, Volume Slider, and live playback state.
 */

const VOLUME_STORAGE_KEY = "citadel_music_volume";

let audioEl = null;

function formatTime(sec) {
  if (!Number.isFinite(sec) || sec < 0) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

function playIcon() {
  return `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><polygon points="6,4 20,12 6,20"></polygon></svg>`;
}

function pauseIcon() {
  return `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>`;
}

function volumeOnIcon() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
  </svg>`;
}

function volumeOffIcon() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
    <line x1="23" y1="9" x2="17" y2="15"></line>
    <line x1="17" y1="9" x2="23" y2="15"></line>
  </svg>`;
}

export function initMusicPlayer(container) {
  if (!container) return;

  let savedVol = 0.5;
  try {
    const raw = localStorage.getItem(VOLUME_STORAGE_KEY);
    if (raw !== null) {
      const parsed = parseFloat(raw);
      if (Number.isFinite(parsed) && parsed >= 0 && parsed <= 1) savedVol = parsed;
    }
  } catch (_err) {
    // ignore
  }

  container.innerHTML = `
    <audio id="citadel-bg-audio" preload="metadata" loop>
      <source src="/assets/music/citadel_theme.mp3" type="audio/mpeg" />
      <source src="/assets/music/citade_v.1.0.m.1.mp4" type="audio/mp4" />
    </audio>
    <button type="button" id="music-play-btn" class="music-btn" aria-label="Play Citadel Theme" title="Play / Pause">
      ${playIcon()}
    </button>
    <div class="music-meta">
      <span class="music-track-title">CITADEL Theme</span>
      <span id="music-state-label" class="music-state mono">Paused &middot; 0:00</span>
    </div>
    <div class="music-volume-wrap">
      <button type="button" id="music-mute-btn" class="music-btn" aria-label="Mute or Unmute" title="Mute / Unmute">
        ${volumeOnIcon()}
      </button>
      <input
        type="range"
        id="music-volume-slider"
        class="music-volume-slider"
        min="0"
        max="100"
        value="${Math.round(savedVol * 100)}"
        aria-label="Music volume"
      />
    </div>
  `;

  audioEl = container.querySelector("#citadel-bg-audio");
  const playBtn = container.querySelector("#music-play-btn");
  const muteBtn = container.querySelector("#music-mute-btn");
  const volumeSlider = container.querySelector("#music-volume-slider");
  const stateLabel = container.querySelector("#music-state-label");

  audioEl.volume = savedVol;

  function syncUi() {
    const isPlaying = !audioEl.paused;
    const isMuted = audioEl.muted || audioEl.volume === 0;
    playBtn.innerHTML = isPlaying ? pauseIcon() : playIcon();
    playBtn.classList.toggle("playing", isPlaying);
    playBtn.setAttribute("aria-label", isPlaying ? "Pause Citadel Theme" : "Play Citadel Theme");

    muteBtn.innerHTML = isMuted ? volumeOffIcon() : volumeOnIcon();
    muteBtn.setAttribute("aria-label", isMuted ? "Unmute Citadel Theme" : "Mute Citadel Theme");

    let statusText = "Paused";
    if (isPlaying) {
      statusText = isMuted ? "Muted" : "Playing";
    }
    const timePart = audioEl.duration
      ? `${formatTime(audioEl.currentTime)} / ${formatTime(audioEl.duration)}`
      : formatTime(audioEl.currentTime);
    stateLabel.textContent = `${statusText} · ${timePart}`;

    window.dispatchEvent(
      new CustomEvent("citadel:musicstate", {
        detail: { isPlaying, isMuted },
      })
    );
  }

  async function togglePlayback() {
    if (audioEl.paused) {
      try {
        await audioEl.play();
      } catch (_err) {
        stateLabel.textContent = "Click Play to start";
      }
    } else {
      audioEl.pause();
    }
    syncUi();
  }

  playBtn.addEventListener("click", togglePlayback);

  muteBtn.addEventListener("click", () => {
    audioEl.muted = !audioEl.muted;
    syncUi();
  });

  volumeSlider.addEventListener("input", () => {
    const val = Number(volumeSlider.value) / 100;
    audioEl.volume = val;
    if (val > 0 && audioEl.muted) {
      audioEl.muted = false;
    }
    try {
      localStorage.setItem(VOLUME_STORAGE_KEY, String(val));
    } catch (_err) {
      // ignore
    }
    syncUi();
  });

  audioEl.addEventListener("timeupdate", syncUi);
  audioEl.addEventListener("loadedmetadata", syncUi);
  audioEl.addEventListener("play", syncUi);
  audioEl.addEventListener("pause", syncUi);

  // Allow hero button to toggle playback directly
  window.citadelToggleMusic = togglePlayback;
  window.citadelIsMusicPlaying = () => Boolean(audioEl && !audioEl.paused);

  syncUi();
}
