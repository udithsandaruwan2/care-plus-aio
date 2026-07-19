/**
 * Browser TTS for Serah replies. Picks a voice matching reply_lang when possible.
 */
export function speakSerah(text: string, lang: string): Promise<void> {
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

export function stopSpeaking() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}
