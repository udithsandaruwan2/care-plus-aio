import type { RecognitionLang } from './uiVoiceLanguage';

/**
 * @deprecated Prefer uiLanguageToRecognition from the language picker.
 * Kept for any legacy call sites.
 */
export function guessRecognitionLang(_text?: string): RecognitionLang {
  return 'si-LK';
}

export function recognitionLangLabel(lang: RecognitionLang): string {
  switch (lang) {
    case 'si-LK':
      return 'සිංහල';
    case 'ta-LK':
      return 'தமிழ்';
    default:
      return 'English';
  }
}
