/**
 * Browser / server TTS for Serah replies.
 * Prefers server audio (base64) when present; falls back to speechSynthesis
 * only when the browser actually has a matching voice (Sinhala/Tamil usually do not).
 *
 * Step 85: speaking is abortable and observable so barge-in can interrupt playback.
 */

let currentAudio: HTMLAudioElement | null = null;
let voicesReady: Promise<SpeechSynthesisVoice[]> | null = null;
let speaking = false;
let speakResolve: (() => void) | null = null;
const speakingListeners = new Set<(active: boolean) => void>();

function notifySpeaking(active: boolean) {
  if (speaking === active) return;
  speaking = active;
  speakingListeners.forEach((fn) => fn(active));
}

export function isSerahSpeaking(): boolean {
  return speaking;
}

/** Subscribe to Serah playback start/stop (Step 85 barge-in). */
export function subscribeSerahSpeaking(fn: (active: boolean) => void): () => void {
  speakingListeners.add(fn);
  return () => {
    speakingListeners.delete(fn);
  };
}

function clearPlayback() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  if (currentAudio) {
    currentAudio.onended = null;
    currentAudio.onerror = null;
    currentAudio.pause();
    currentAudio.src = '';
    currentAudio = null;
  }
}

function resolveSpeak() {
  const r = speakResolve;
  speakResolve = null;
  r?.();
}

/** Stop Serah audio and notify listeners that playback ended. */
export function stopSpeaking() {
  clearPlayback();
  resolveSpeak();
  notifySpeaking(false);
}

function playServerAudio(
  b64: string,
  mime: string,
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
      const finish = () => {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
        if (speakResolve === resolve) {
          speakResolve = null;
          notifySpeaking(false);
          resolve();
        }
      };
      audio.onended = finish;
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
        void fallback().then(() => {
          if (speakResolve === resolve) {
            speakResolve = null;
            notifySpeaking(false);
            resolve();
          }
        });
      };
      void audio.play().catch(() => {
        URL.revokeObjectURL(url);
        if (currentAudio === audio) currentAudio = null;
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

export function speakSerah(
  text: string,
  lang: string,
  opts?: { audioBase64?: string | null; audioMime?: string | null },
): Promise<void> {
  // Replace playback without emitting a false→true flicker (keeps barge watch alive).
  clearPlayback();
  resolveSpeak();
  notifySpeaking(true);
  const b64 = (opts?.audioBase64 || '').trim();
  const mime = (opts?.audioMime || 'audio/wav').trim() || 'audio/wav';
  if (b64 && typeof window !== 'undefined') {
    return playServerAudio(b64, mime, () => speakBrowser(text, lang));
  }
  return speakBrowser(text, lang);
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
  return (
    voices.find((v) => v.lang.toLowerCase() === target.toLowerCase()) ||
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ||
    voices.find((v) => v.lang.toLowerCase().includes(prefix))
  );
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
  utter.rate = 0.98;
  if (match) utter.voice = match;

  return new Promise((resolve) => {
    speakResolve = resolve;
    utter.onend = () => {
      if (speakResolve === resolve) {
        speakResolve = null;
        notifySpeaking(false);
        resolve();
      }
    };
    utter.onerror = () => {
      if (speakResolve === resolve) {
        speakResolve = null;
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
