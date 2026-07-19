/** UI voice language — locks captions, ASR, and Serah reply language. */
export type UiVoiceLanguage = 'Sinhala' | 'Tamil' | 'English';

export type RecognitionLang = 'si-LK' | 'ta-LK' | 'en-US';

const STORAGE_KEY = 'careplus.uiVoiceLanguage';

export function loadUiVoiceLanguage(): UiVoiceLanguage {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === 'Sinhala' || raw === 'Tamil' || raw === 'English') return raw;
  } catch {
    /* ignore */
  }
  return 'Sinhala';
}

export function saveUiVoiceLanguage(lang: UiVoiceLanguage): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* ignore */
  }
}

export function uiLanguageToRecognition(lang: UiVoiceLanguage): RecognitionLang {
  switch (lang) {
    case 'Sinhala':
      return 'si-LK';
    case 'Tamil':
      return 'ta-LK';
    default:
      return 'en-US';
  }
}

export function uiLanguageToBcp47(lang: UiVoiceLanguage): string {
  return uiLanguageToRecognition(lang);
}

export function uiLanguageLabel(lang: UiVoiceLanguage): string {
  switch (lang) {
    case 'Sinhala':
      return 'සිංහල';
    case 'Tamil':
      return 'தமிழ்';
    default:
      return 'English';
  }
}

export const UI_VOICE_LANGUAGES: UiVoiceLanguage[] = ['Sinhala', 'Tamil', 'English'];
