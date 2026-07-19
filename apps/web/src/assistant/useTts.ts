/**
 * Browser / server TTS for Serah replies.
 * Prefers server audio (base64) when present; falls back to speechSynthesis.
 */

let currentAudio: HTMLAudioElement | null = null;

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

function speakBrowser(text: string, lang: string): Promise<void> {
  if (typeof window === 'undefined' || !window.speechSynthesis || !text.trim()) {
    return Promise.resolve();
  }
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = lang || 'en-US';
  utter.rate = 1.02;

  const voices = window.speechSynthesis.getVoices();
  const prefix = (lang || 'en').slice(0, 2).toLowerCase();
  const match =
    voices.find((v) => v.lang.toLowerCase() === lang.toLowerCase()) ||
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix));
  if (match) utter.voice = match;

  return new Promise((resolve) => {
    utter.onend = () => resolve();
    utter.onerror = () => resolve();
    window.speechSynthesis.speak(utter);
  });
}
