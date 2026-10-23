/**
 * The page's own voice: Chrome's speechSynthesis.
 *
 * The server sends `{"type": "speak"}` instead of `{"type": "audio"}` when it
 * has no audio of its own for a sentence — no Fish Audio key, or a request
 * that failed (see tts.py, `JARVIS_TTS`). This keeps the audio player's whole
 * contract, because everything on the server hangs off it:
 *
 *   * sentences are spoken strictly in order;
 *   * each one is acknowledged (`onPlayed`) when it FINISHES — echo rejection
 *     treats his words as coming out of the speaker until then, and every
 *     read-back waits for that ack before it opens its cancel window;
 *   * `stop()` silences at once and acks nothing (the server has already
 *     settled what was in flight), `dropQueued()` keeps only the sentence
 *     being spoken.
 *
 * speechSynthesis plays outside Web Audio, so there is no analyser to drive
 * the orb. `levels()` supplies a stand-in: the envelope `scripts/make_orb_loop.py`
 * fitted to the real analyser's readings of speech (bass ~0.62–0.87, mid
 * ~0.35–0.64, a 4.5 Hz syllable), dipped at the pauses the voice reports.
 */

export interface Levels {
  bass: number;
  mid: number;
}

export interface BrowserSpeaker {
  /** Whether this browser can speak at all. */
  readonly available: boolean;
  enqueue(text: string, utt: number, idx: number): void;
  stop(): void;
  dropQueued(): void;
  setLang(lang: string): void;
  setVoiceHint(hint: string): void;
  onPlayed(cb: (utt: number, idx: number) => void): void;
  onNeedsGesture(cb: () => void): void;
  /** The synthetic envelope while speaking, else null. */
  levels(): Levels | null;
  /** Speak a sample now, outside the queue (the settings panel's "test"). */
  sample(text: string): void;
}

interface Item {
  utt: number;
  idx: number;
  text: string;
  u: SpeechSynthesisUtterance | null; // held: Chrome drops `onend` for a collected utterance
  startedAt: number;
}

// Voices that suit a butler, best first. Matched against the voice's name;
// the first one this machine actually has wins. macOS ships Daniel (en-GB).
const ENGLISH_PREFERENCE = ["Daniel", "Arthur", "Google UK English Male", "Oliver", "Malcolm",
                            "Reed (English (UK))", "Rocko (English (UK))"];

// How long a sentence can plausibly take, generously, so a voice that never
// reports its end (Chrome's network voices stop firing `onend` past ~15s)
// cannot wedge the queue: ~4 Han characters a second, ~12 Latin letters.
function deadlineMs(text: string): number {
  let han = 0;
  for (const ch of text) if (/[㐀-鿿豈-﫿]/.test(ch)) han++;
  const latin = text.length - han;
  const seconds = han / 4 + latin / 12;
  // ...and under the server's 45s ack timeout, which would give up first.
  return Math.min(40000, Math.max(4000, seconds * 2000 + 4000));
}

const PAUSE_MARKS = new Set(["，", "。", "、", "；", "：", "！", "？", ",", ".", ";", ":", "!", "?", "—"]);

export function createBrowserSpeaker(): BrowserSpeaker {
  const synth: SpeechSynthesis | null =
    typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : null;

  const queue: Item[] = [];
  let current: Item | null = null;
  let lang = "en-US";
  let hint = "";
  let voice: SpeechSynthesisVoice | null = null;
  let playedCb: ((utt: number, idx: number) => void) | null = null;
  let gestureCb: (() => void) | null = null;
  let gestureNoticeShown = false;
  let waitingForGesture = false;
  let watchdog: ReturnType<typeof setTimeout> | null = null;
  let keepAlive: ReturnType<typeof setInterval> | null = null;
  let speakingSince = 0;
  let releasedAt = 0;
  let pauseAt = 0;

  function chooseVoice() {
    if (!synth) return;
    const voices = synth.getVoices();
    if (!voices.length) return; // not loaded yet; `voiceschanged` calls again
    const norm = (l: string) => l.replace("_", "-").toLowerCase();
    const want = norm(lang);
    const byName = (needle: string) =>
      voices.find((v) => v.name.toLowerCase().includes(needle.toLowerCase())) || null;

    let pick: SpeechSynthesisVoice | null = hint ? byName(hint) : null;
    if (!pick && want.startsWith("zh")) {
      // Taiwan Mandarin first; then any Mandarin (it reads Traditional
      // characters perfectly well). Cantonese (zh-HK) only as a last resort:
      // it would read Mandarin text as Cantonese.
      const tiers = [
        (v: SpeechSynthesisVoice) => norm(v.lang) === "zh-tw",
        (v: SpeechSynthesisVoice) => norm(v.lang).startsWith("zh") && !norm(v.lang).includes("hk"),
        (v: SpeechSynthesisVoice) => norm(v.lang).startsWith("zh"),
      ];
      for (const tier of tiers) {
        const matches = voices.filter(tier);
        // Local voices first: they report their end reliably and work offline.
        pick = matches.find((v) => v.localService) || matches[0] || null;
        if (pick) break;
      }
    }
    if (!pick && want.startsWith("en")) {
      for (const name of ENGLISH_PREFERENCE) {
        pick = voices.find((v) => v.name === name || v.name.startsWith(name)) || null;
        if (pick) break;
      }
      pick = pick || voices.find((v) => norm(v.lang) === "en-gb") ||
        voices.find((v) => norm(v.lang).startsWith("en")) || null;
    }
    voice = pick;
    if (voice) console.info(`[voice] speaking with ${voice.name} (${voice.lang})`);
  }

  if (synth) {
    synth.addEventListener?.("voiceschanged", chooseVoice);
    chooseVoice();
  }

  function clearTimers() {
    if (watchdog) { clearTimeout(watchdog); watchdog = null; }
    if (keepAlive) { clearInterval(keepAlive); keepAlive = null; }
  }

  function finish(item: Item) {
    if (current !== item) return; // stopped, or already finished by the watchdog
    clearTimers();
    current = null;
    releasedAt = performance.now();
    playedCb?.(item.utt, item.idx);
    next();
  }

  function activated(): boolean {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ua = (navigator as any).userActivation;
    return !ua || ua.hasBeenActive;
  }

  function waitForGesture() {
    if (waitingForGesture) return;
    waitingForGesture = true;
    if (!gestureNoticeShown) {
      gestureNoticeShown = true;
      gestureCb?.();
    }
    const go = () => {
      window.removeEventListener("pointerdown", go, true);
      window.removeEventListener("keydown", go, true);
      waitingForGesture = false;
      next();
    };
    window.addEventListener("pointerdown", go, true);
    window.addEventListener("keydown", go, true);
  }

  function next() {
    if (current || !queue.length) return;
    if (!synth) {
      // Nothing can speak: ack in order so the server's sequence advances,
      // exactly as the audio player does for a chunk it cannot decode.
      while (queue.length) {
        const dead = queue.shift()!;
        console.log("[JARVIS]", dead.text);
        playedCb?.(dead.utt, dead.idx);
      }
      return;
    }
    if (!activated()) {
      // Chrome refuses speech before the page has had a click. Wait for one
      // and carry on from here — the same as the audio player's gesture wait.
      waitForGesture();
      return;
    }
    const item = queue.shift()!;
    current = item;
    const u = new SpeechSynthesisUtterance(item.text);
    u.lang = lang;
    if (voice) u.voice = voice;
    u.rate = 1.0;
    u.pitch = 1.0;
    item.u = u;
    u.onstart = () => {
      if (current !== item) return;
      item.startedAt = performance.now();
      speakingSince = item.startedAt;
    };
    u.onboundary = (ev: SpeechSynthesisEvent) => {
      if (current !== item) return;
      const before = item.text.slice(Math.max(0, ev.charIndex - 2), ev.charIndex);
      if ([...before].some((c) => PAUSE_MARKS.has(c))) pauseAt = performance.now();
    };
    u.onend = () => finish(item);
    u.onerror = (ev: SpeechSynthesisErrorEvent) => {
      if (current !== item) return; // our own cancel(): nothing to ack
      if (ev.error === "not-allowed") {
        // No gesture yet after all. Put it back and wait for one.
        clearTimers();
        current = null;
        queue.unshift(item);
        waitForGesture();
        return;
      }
      console.warn("[voice] could not speak:", ev.error);
      finish(item); // acked anyway, in order, like an undecodable chunk
    };
    // A voice that never says it ended must not stall everything behind it.
    watchdog = setTimeout(() => {
      if (current === item) {
        console.warn("[voice] no end reported; moving on");
        synth.cancel();
        finish(item);
      }
    }, deadlineMs(item.text));
    // Chrome's network voices go quiet mid-sentence after ~15s unless nudged.
    keepAlive = setInterval(() => {
      if (current === item && synth.speaking) synth.resume();
    }, 10000);
    synth.speak(u);
  }

  return {
    available: synth !== null,

    enqueue(text: string, utt: number, idx: number) {
      queue.push({ utt, idx, text, u: null, startedAt: 0 });
      next();
    },

    stop() {
      queue.length = 0;
      const was = current;
      current = null; // so its onend/onerror does not ack or chain
      clearTimers();
      if (was) releasedAt = performance.now();
      synth?.cancel();
    },

    dropQueued() {
      // As the audio player: keep the one speaking, or — if nothing has
      // started — the head the server is still waiting to hear about.
      queue.length = current ? 0 : Math.min(queue.length, 1);
    },

    setLang(next: string) {
      if (next && next !== lang) {
        lang = next;
        chooseVoice();
      }
    },

    setVoiceHint(next: string) {
      if ((next || "") !== hint) {
        hint = next || "";
        chooseVoice();
      }
    },

    onPlayed(cb) {
      playedCb = cb;
    },

    onNeedsGesture(cb) {
      gestureCb = cb;
    },

    levels(): Levels | null {
      const now = performance.now();
      if (!current || !current.startedAt) {
        // Release: fall away over 150ms rather than snapping to nothing.
        const since = now - releasedAt;
        if (releasedAt && since < 150) {
          const k = 1 - since / 150;
          return { bass: 0.6 * k, mid: 0.35 * k };
        }
        return null;
      }
      const t = (now - speakingSince) / 1000;
      const attack = Math.min(1, t / 0.12);
      const syllable = Math.pow(0.5 - 0.5 * Math.cos(2 * Math.PI * 4.5 * t), 1.6);
      const swell = 0.85 + 0.15 * Math.sin(2 * Math.PI * 0.35 * t + 0.7);
      const flutter = 1 + 0.04 * Math.sin(2 * Math.PI * 3.5 * t);
      const gap = now - pauseAt < 180 ? 0.15 : 1;
      const k = attack * swell * flutter * gap;
      return { bass: (0.62 + 0.25 * syllable) * k, mid: (0.36 + 0.26 * syllable) * k };
    },

    sample(text: string) {
      if (!synth) return;
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang;
      if (voice) u.voice = voice;
      synth.speak(u);
    },
  };
}
