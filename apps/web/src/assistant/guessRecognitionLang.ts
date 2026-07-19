import type { RecognitionLang } from './useSpeechRecognition';

const SINHALA = /[\u0D80-\u0DFF]/;
const TAMIL = /[\u0B80-\u0BFF]/;

/**
 * Pick a Web Speech `lang` from transcript script, then browser locale.
 *
 * Important: Chrome's Web Speech for si-LK / ta-LK is unreliable and often
 * returns English-only. Captions are best-effort; real multilingual ASR is
 * server-side (Gemini audio / future faster-whisper) via ``/voice/turn/``.
 */
export function guessRecognitionLang(text?: string): RecognitionLang {
  const sample = (text ?? '').trim();
  if (SINHALA.test(sample)) return 'si-LK';
  if (TAMIL.test(sample)) return 'ta-LK';

  const nav = (typeof navigator !== 'undefined' ? navigator.language : '') || '';
  const lower = nav.toLowerCase();
  if (lower.startsWith('si')) return 'si-LK';
  if (lower.startsWith('ta')) return 'ta-LK';
  if (lower.startsWith('en')) return 'en-US';
  // Sri Lanka–first captions; server ASR still owns correctness.
  return 'si-LK';
}

export function recognitionLangLabel(lang: RecognitionLang): string {
  switch (lang) {
    case 'si-LK':
      return 'සිංහල auto';
    case 'ta-LK':
      return 'தமிழ் auto';
    default:
      return 'EN auto';
  }
}
