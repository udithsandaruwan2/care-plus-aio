export type UiVoiceLanguage = 'Sinhala' | 'Tamil' | 'English';

let cached: UiVoiceLanguage = 'English';

export function loadUiVoiceLanguage(): UiVoiceLanguage {
  return cached;
}

export function saveUiVoiceLanguage(lang: UiVoiceLanguage): void {
  cached = lang;
}
