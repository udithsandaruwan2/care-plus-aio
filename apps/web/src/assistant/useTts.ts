/**
 * Browser / server TTS for Serah replies.
 * Prefers server audio (base64) when present; falls back to speechSynthesis.
 */

let currentAudio: HTMLAudioElement | null = null;
let voicesReady: Promise<SpeechSynthesisVoice[]> | null = null;

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

export function stopSpeaking() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = '';
    currentAudio = null;
  }
}

export function speakSerah(
  text: string,
  lang: string,
  opts?: { audioBase64?: string | null; audioMime?: string | null },
): Promise<void> {
  stopSpeaking();
  const b64 = (opts?.audioBase64 || '').trim();
  const mime = (opts?.audioMime || 'audio/wav').trim() || 'audio/wav';
  if (b64 && typeof window !== 'undefined') {
    return new Promise((resolve) => {
      try {
        const src = `data:${mime};base64,${b64}`;
        const audio = new Audio(src);
        currentAudio = audio;
        audio.onended = () => {
          currentAudio = null;
          resolve();
        };
        audio.onerror = () => {
          currentAudio = null;
          void speakBrowser(text, lang).then(resolve);
        };
        void audio.play().catch(() => {
          currentAudio = null;
          void speakBrowser(text, lang).then(resolve);
        });
      } catch {
        void speakBrowser(text, lang).then(resolve);
      }
    });
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

async function speakBrowser(text: string, lang: string): Promise<void> {
  if (typeof window === 'undefined' || !window.speechSynthesis || !text.trim()) {
    return;
  }
  const target = normalizeLang(lang);
  const prefix = target.slice(0, 2).toLowerCase();
  window.speechSynthesis.cancel();
  const voices = await loadBrowserVoices();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = target;
  utter.rate = 0.98;

  const match =
    voices.find((v) => v.lang.toLowerCase() === target.toLowerCase()) ||
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ||
    voices.find((v) => v.lang.toLowerCase().includes(prefix));
  if (match) utter.voice = match;

  return new Promise((resolve) => {
    utter.onend = () => resolve();
    utter.onerror = () => resolve();
    window.speechSynthesis.speak(utter);
  });
}
