/**
 * Browser / server TTS for Serah replies.
 * Prefers server audio (base64) when present; falls back to speechSynthesis
 * only when the browser actually has a matching voice (Sinhala/Tamil usually do not).
 *
 * Near-field barge-in: interruptSpeaking() pauses/snapshots residual so the
 * truncated reply can resume before the next turn's audio.
 */

export type SpeakOpts = {
  audioBase64?: string | null;
  audioMime?: string | null;
};

export type SpeakJob = {
  text: string;
  lang: string;
  opts?: SpeakOpts;
};

export type InterruptedResidual =
  | {
      kind: 'server';
      audio: HTMLAudioElement;
      objectUrl: string;
      offsetSec: number;
      text: string;
      lang: string;
    }
  | {
      kind: 'text';
      text: string;
      lang: string;
    };

type ActiveUtterance = {
  text: string;
  lang: string;
  mode: 'server' | 'browser';
  startedAt: number;
  rate: number;
  objectUrl?: string;
};

let currentAudio: HTMLAudioElement | null = null;
let voicesReady: Promise<SpeechSynthesisVoice[]> | null = null;
let speaking = false;
let speakResolve: (() => void) | null = null;
let activeUtterance: ActiveUtterance | null = null;
let heldResidual: InterruptedResidual | null = null;
let speakQueue: SpeakJob[] = [];
let drainingQueue = false;
const speakingListeners = new Set<(active: boolean) => void>();

function notifySpeaking(active: boolean) {
  if (speaking === active) return;
  speaking = active;
  speakingListeners.forEach((fn) => fn(active));
}

export function isSerahSpeaking(): boolean {
  return speaking;
}

/** Subscribe to Serah playback start/stop (barge-in). */
export function subscribeSerahSpeaking(fn: (active: boolean) => void): () => void {
  speakingListeners.add(fn);
  return () => {
    speakingListeners.delete(fn);
  };
}

/** Estimate remaining text after barge-in for browser TTS (no cursor API). */
export function estimateRemainingText(
  text: string,
  elapsedMs: number,
  rate = 0.92,
): string {
  const trimmed = text.trim();
  if (!trimmed) return '';
  // ~14 chars/sec at rate 1.0 for English-like speech; scale by rate.
  const charsPerSec = 14 * rate;
  const spoken = Math.floor((elapsedMs / 1000) * charsPerSec);
  if (spoken <= 0) return trimmed;
  if (spoken >= trimmed.length) return '';
  let cut = spoken;
  // Prefer a word boundary so resume does not start mid-word.
  const space = trimmed.lastIndexOf(' ', cut);
  if (space > cut * 0.5) cut = space + 1;
  return trimmed.slice(cut).trim();
}

function clearPlaybackHard() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  if (currentAudio) {
    currentAudio.onended = null;
    currentAudio.onerror = null;
    currentAudio.pause();
    if (activeUtterance?.objectUrl) {
      URL.revokeObjectURL(activeUtterance.objectUrl);
    }
    currentAudio.src = '';
    currentAudio = null;
  }
  activeUtterance = null;
}

function resolveSpeak() {
  const r = speakResolve;
  speakResolve = null;
  r?.();
}

function discardHeldResidual() {
  if (heldResidual?.kind === 'server') {
    heldResidual.audio.onended = null;
    heldResidual.audio.onerror = null;
    heldResidual.audio.pause();
    URL.revokeObjectURL(heldResidual.objectUrl);
    heldResidual.audio.src = '';
  }
  heldResidual = null;
}

/** Stop active playback and queue; leave a barge residual intact. */
export function stopActivePlayback() {
  speakQueue = [];
  drainingQueue = false;
  clearPlaybackHard();
  resolveSpeak();
  notifySpeaking(false);
}

/** Hard stop: drop queue, residual, and active playback. */
export function stopSpeaking() {
  discardHeldResidual();
  stopActivePlayback();
}

/**
 * Barge-in stop: pause server audio (or estimate remaining browser text) and
 * keep a residual for later resume. Does not clear the speak queue entry for
 * the new reply (caller enqueues after the turn).
 */
export function interruptSpeaking(): InterruptedResidual | null {
  speakQueue = [];
  drainingQueue = false;
  const utter = activeUtterance;
  const audio = currentAudio;
  let residual: InterruptedResidual | null = null;

  if (utter?.mode === 'server' && audio && utter.objectUrl) {
    const offset = audio.currentTime || 0;
    const remaining = Math.max(0, (audio.duration || 0) - offset);
    audio.onended = null;
    audio.onerror = null;
    audio.pause();
    if (remaining > 0.35 && Number.isFinite(remaining)) {
      residual = {
        kind: 'server',
        audio,
        objectUrl: utter.objectUrl,
        offsetSec: offset,
        text: utter.text,
        lang: utter.lang,
      };
      // Detach so clear does not revoke/destroy the paused element.
      currentAudio = null;
      activeUtterance = null;
    } else {
      clearPlaybackHard();
    }
  } else if (utter?.mode === 'browser') {
    const elapsed = performance.now() - utter.startedAt;
    const remaining = estimateRemainingText(utter.text, elapsed, utter.rate);
    clearPlaybackHard();
    if (remaining.length > 8) {
      residual = { kind: 'text', text: remaining, lang: utter.lang };
    }
  } else {
    clearPlaybackHard();
  }

  discardHeldResidual();
  heldResidual = residual;
  resolveSpeak();
  notifySpeaking(false);
  return residual;
}

/** Peek without taking (engine may decide empty-barge resume). */
export function peekInterruptedResidual(): InterruptedResidual | null {
  return heldResidual;
}

/** Take ownership of the barge-in residual (clears module hold). */
export function takeInterruptedResidual(): InterruptedResidual | null {
  const r = heldResidual;
  heldResidual = null;
  return r;
}

/** Drop residual without speaking it. */
export function clearInterruptedResidual() {
  discardHeldResidual();
}

function playServerAudio(
  b64: string,
  mime: string,
  text: string,
  lang: string,
  fallback: () => Promise<void>,
): Promise<void> {
  return new Promise((resolve) => {
    speakResolve = resolve;
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: mime || 'audio/wav' });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudio = audio;
      activeUtterance = {
        text,
        lang,
        mode: 'server',
        startedAt: performance.now(),
        rate: 1,
        objectUrl: url,
      };
      const finish = () => {
        if (currentAudio === audio) {
          URL.revokeObjectURL(url);
          currentAudio = null;
          activeUtterance = null;
        }
        if (speakResolve === resolve) {
          speakResolve = null;
          notifySpeaking(false);
          resolve();
        }
      };
      audio.onended = finish;
      audio.onerror = () => {
        if (currentAudio === audio) {
          URL.revokeObjectURL(url);
          currentAudio = null;
          activeUtterance = null;
        }
        void fallback().then(() => {
          if (speakResolve === resolve) {
            speakResolve = null;
            notifySpeaking(false);
            resolve();
          }
        });
      };
      void audio.play().catch(() => {
        if (currentAudio === audio) {
          URL.revokeObjectURL(url);
          currentAudio = null;
          activeUtterance = null;
        }
        void fallback().then(() => {
          if (speakResolve === resolve) {
            speakResolve = null;
            notifySpeaking(false);
            resolve();
          }
        });
      });
    } catch {
      void fallback().then(() => {
        if (speakResolve === resolve) {
          speakResolve = null;
          notifySpeaking(false);
          resolve();
        }
      });
    }
  });
}

export function speakSerah(text: string, lang: string, opts?: SpeakOpts): Promise<void> {
  // Replace playback without emitting a false→true flicker (keeps barge watch alive).
  clearPlaybackHard();
  resolveSpeak();
  notifySpeaking(true);
  const b64 = (opts?.audioBase64 || '').trim();
  const mime = (opts?.audioMime || 'audio/wav').trim() || 'audio/wav';
  if (b64 && typeof window !== 'undefined') {
    return playServerAudio(b64, mime, text, lang, () => speakBrowser(text, lang));
  }
  return speakBrowser(text, lang);
}

/** Resume a barge-in residual from the stop point. */
export function resumeResidual(residual: InterruptedResidual): Promise<void> {
  if (residual.kind === 'text') {
    if (!residual.text.trim()) {
      notifySpeaking(false);
      return Promise.resolve();
    }
    return speakSerah(residual.text, residual.lang);
  }

  clearPlaybackHard();
  resolveSpeak();
  notifySpeaking(true);
  const { audio, objectUrl, offsetSec, text, lang } = residual;
  currentAudio = audio;
  activeUtterance = {
    text,
    lang,
    mode: 'server',
    startedAt: performance.now(),
    rate: 1,
    objectUrl,
  };
  try {
    audio.currentTime = offsetSec;
  } catch {
    /* some browsers reject seek before metadata */
  }
  return new Promise((resolve) => {
    speakResolve = resolve;
    const finish = () => {
      if (currentAudio === audio) {
        URL.revokeObjectURL(objectUrl);
        currentAudio = null;
        activeUtterance = null;
      }
      if (speakResolve === resolve) {
        speakResolve = null;
        notifySpeaking(false);
        resolve();
      }
    };
    audio.onended = finish;
    audio.onerror = finish;
    void audio.play().catch(finish);
  });
}

async function drainSpeakQueue(): Promise<void> {
  if (drainingQueue) return;
  drainingQueue = true;
  try {
    while (speakQueue.length) {
      const job = speakQueue.shift()!;
      await speakSerah(job.text, job.lang, job.opts);
    }
  } finally {
    drainingQueue = false;
  }
}

/**
 * Queue residual (if any) then the new reply so routing is:
 * finish interrupted speech → speak new output.
 */
export function enqueueAfterBargeIn(
  residual: InterruptedResidual | null,
  next: SpeakJob | null,
): Promise<void> {
  return (async () => {
    if (residual) {
      await resumeResidual(residual);
    }
    if (next?.text.trim()) {
      await speakSerah(next.text, next.lang, next.opts);
    }
  })();
}

/** Append a speak job; plays after any in-flight drain. */
export function enqueueSpeak(job: SpeakJob): void {
  speakQueue.push(job);
  void drainSpeakQueue();
}

function normalizeLang(lang: string): string {
  if (!lang) return 'en-US';
  if (lang === 'Sinhala' || lang.startsWith('si')) return 'si-LK';
  if (lang === 'Tamil' || lang.startsWith('ta')) return 'ta-LK';
  if (lang === 'English' || lang.startsWith('en')) return 'en-US';
  return lang;
}

function pickVoice(
  voices: SpeechSynthesisVoice[],
  target: string,
): SpeechSynthesisVoice | undefined {
  const prefix = target.slice(0, 2).toLowerCase();
  const sameLang = voices.filter(
    (v) =>
      v.lang.toLowerCase() === target.toLowerCase() ||
      v.lang.toLowerCase().startsWith(prefix),
  );
  const pool = sameLang.length ? sameLang : voices;
  const scored = [...pool].sort((a, b) => voiceQuality(b, prefix) - voiceQuality(a, prefix));
  return scored[0];
}

function voiceQuality(voice: SpeechSynthesisVoice, prefix: string): number {
  const name = `${voice.name} ${voice.lang}`.toLowerCase();
  let score = 0;
  if (voice.lang.toLowerCase().startsWith(prefix)) score += 20;
  if (voice.localService) score += 4;
  if (voice.default) score += 2;
  if (/neural|natural|premium|enhanced|online \(natural\)/.test(name)) score += 12;
  if (/google|microsoft|samantha|siri|aria|jenny|guy/.test(name)) score += 8;
  if (/compact|eloquence/.test(name)) score -= 6;
  return score;
}

async function speakBrowser(text: string, lang: string): Promise<void> {
  if (typeof window === 'undefined' || !window.speechSynthesis || !text.trim()) {
    notifySpeaking(false);
    return;
  }
  const target = normalizeLang(lang);
  const prefix = target.slice(0, 2).toLowerCase();
  const voices = await loadBrowserVoices();
  if (!speaking) return;
  const match = pickVoice(voices, target);
  // Chrome/Linux has no Sinhala or Tamil voices — speaking anyway is silent.
  if (!match && (prefix === 'si' || prefix === 'ta')) {
    notifySpeaking(false);
    return;
  }
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = target;
  utter.rate = 0.92;
  utter.pitch = 1.02;
  if (match) utter.voice = match;
  activeUtterance = {
    text,
    lang,
    mode: 'browser',
    startedAt: performance.now(),
    rate: utter.rate,
  };

  return new Promise((resolve) => {
    speakResolve = resolve;
    utter.onend = () => {
      if (speakResolve === resolve) {
        speakResolve = null;
        activeUtterance = null;
        notifySpeaking(false);
        resolve();
      }
    };
    utter.onerror = () => {
      if (speakResolve === resolve) {
        speakResolve = null;
        activeUtterance = null;
        notifySpeaking(false);
        resolve();
      }
    };
    window.speechSynthesis.speak(utter);
  });
}

function loadBrowserVoices(): Promise<SpeechSynthesisVoice[]> {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    return Promise.resolve([]);
  }
  if (!voicesReady) {
    voicesReady = new Promise((resolve) => {
      const synth = window.speechSynthesis;
      const pick = () => {
        const voices = synth.getVoices();
        if (voices.length) resolve(voices);
      };
      pick();
      synth.onvoiceschanged = () => {
        pick();
        resolve(synth.getVoices());
      };
      window.setTimeout(() => resolve(synth.getVoices()), 400);
    });
  }
  return voicesReady;
}
