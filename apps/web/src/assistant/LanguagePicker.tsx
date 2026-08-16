import type { KeyboardEvent } from 'react';
import type { UiVoiceLanguage } from './uiVoiceLanguage';
import { UI_VOICE_LANGUAGES, uiLanguageLabel } from './uiVoiceLanguage';

type Props = {
  value: UiVoiceLanguage;
  onChange: (lang: UiVoiceLanguage) => void;
  disabled?: boolean;
  className?: string;
};

/**
 * Session language lock for captions + server ASR + Serah replies.
 */
export function LanguagePicker({ value, onChange, disabled, className = '' }: Props) {
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    const idx = UI_VOICE_LANGUAGES.indexOf(value);
    if (idx < 0) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      onChange(UI_VOICE_LANGUAGES[(idx + 1) % UI_VOICE_LANGUAGES.length]);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      onChange(
        UI_VOICE_LANGUAGES[(idx - 1 + UI_VOICE_LANGUAGES.length) % UI_VOICE_LANGUAGES.length],
      );
    } else if (e.key === 'Home') {
      e.preventDefault();
      onChange(UI_VOICE_LANGUAGES[0]);
    } else if (e.key === 'End') {
      e.preventDefault();
      onChange(UI_VOICE_LANGUAGES[UI_VOICE_LANGUAGES.length - 1]);
    }
  }

  return (
    <div
      className={`flex flex-wrap items-center justify-center gap-2 ${className}`}
      role="radiogroup"
      aria-label="Conversation language"
      onKeyDown={onKeyDown}
    >
      {UI_VOICE_LANGUAGES.map((lang) => {
        const selected = value === lang;
        return (
          <button
            key={lang}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            disabled={disabled}
            onClick={() => onChange(lang)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition focus-visible:ring-2 focus-visible:ring-cyan disabled:opacity-50 ${
              selected
                ? 'border-cyan bg-cyan/15 text-cyan'
                : 'border-hair text-muted hover:border-cyan/60 hover:text-mist'
            }`}
          >
            {uiLanguageLabel(lang)}
          </button>
        );
      })}
    </div>
  );
}
