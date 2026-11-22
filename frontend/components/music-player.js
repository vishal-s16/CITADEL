/**
 * CITADEL Persistent Background Music Player
 * - Plays theme music automatically once entered (with browser autoplay unlock fallback).
 * - Compact 4x4 square box in the top-right corner (no per-slide volume slider bar).
 * - Persists uninterrupted across SPA route transitions.
 */

let audioEl = null;
let userPaused = false;

function soundOnIcon() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
  </svg>`;
}

function soundOffIcon() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
    <line x1="23" y1="9" x2="17" y2="15"></line>
    <line x1="17" y1="9" x2="23" y2="15"></line>
  </svg>`;
}

export function initMusicPlayer(container) {
  if (!container) return;

  container.innerHTML = `
    <audio id="citadel-bg-audio" preload="auto" loop>
      <source src="/assets/music/citadel_theme.mp3" type="audio/mpeg" />
      <source src="/assets/music/citade_v.1.0.m.1.mp4" type="audio/mp4" />
    </audio>
    <button
      type="button"
      id="music-corner-btn"
      class="music-corner-box"
      aria-label="Toggle CITADEL Theme Music"
      title="CITADEL Theme Music (Click to Mute / Play)"
    >
      ${soundOffIcon()}
    </button>
  `;

  audioEl = container.querySelector("#citadel-bg-audio");
  const cornerBtn = container.querySelector("#music-corner-btn");

  audioEl.volume = 0.5;

  function syncUi() {
    const isPlaying = Boolean(audioEl && !audioEl.paused && !audioEl.muted);
    cornerBtn.innerHTML = isPlaying ? soundOnIcon() : soundOffIcon();
    cornerBtn.classList.toggle("playing", isPlaying);
    cornerBtn.setAttribute(
      "aria-label",
      isPlaying ? "Mute CITADEL Theme Music" : "Play CITADEL Theme Music"
    );
    cornerBtn.setAttribute(
      "title",
      isPlaying ? "CITADEL Theme: Playing (Click to Mute)" : "CITADEL Theme: Off (Click to Play)"
    );

    window.dispatchEvent(
      new CustomEvent("citadel:musicstate", {
        detail: { isPlaying, isMuted: !isPlaying },
      })
    );
  }

  async function startMusic() {
    if (!audioEl || userPaused) return;
    audioEl.muted = false;
    try {
      await audioEl.play();
      syncUi();
    } catch (_err) {
      // Browser blocked autoplay before user gesture; retry on first interaction
      const unlock = async () => {
        window.removeEventListener("pointerdown", unlock);
        window.removeEventListener("keydown", unlock);
        if (!userPaused && audioEl && audioEl.paused) {
          try {
            await audioEl.play();
            syncUi();
          } catch (_e) {
            // ignore
          }
        }
      };
      window.addEventListener("pointerdown", unlock, { once: true });
      window.addEventListener("keydown", unlock, { once: true });
    }
  }

  async function togglePlayback() {
    if (!audioEl) return;
    if (audioEl.paused || audioEl.muted) {
      userPaused = false;
      audioEl.muted = false;
      try {
        await audioEl.play();
      } catch (_err) {
        // ignore
      }
    } else {
      userPaused = true;
      audioEl.pause();
    }
    syncUi();
  }

  cornerBtn.addEventListener("click", togglePlayback);

  audioEl.addEventListener("play", syncUi);
  audioEl.addEventListener("pause", syncUi);
  audioEl.addEventListener("volumechange", syncUi);

  window.citadelStartMusic = startMusic;
  window.citadelToggleMusic = togglePlayback;
  window.citadelIsMusicPlaying = () => Boolean(audioEl && !audioEl.paused && !audioEl.muted);

  syncUi();
}
