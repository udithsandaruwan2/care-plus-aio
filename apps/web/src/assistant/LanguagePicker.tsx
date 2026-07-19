import type { UiVoiceLanguage } from './uiVoiceLanguage';
import { UI_VOICE_LANGUAGES, uiLanguageLabel } from './uiVoiceLanguage';

type Props = {
  value: UiVoiceLanguage;
  onChange: (lang: UiVoiceLanguage) => void;
  disabled?: boolean;
};

/**
 * Session language lock for captions + server ASR + Serah replies.
 */
export function LanguagePicker({ value, onChange, disabled }: Props) {
  return (
    <div
      className="mx-auto mt-4 flex max-w-md flex-wrap items-center justify-center gap-2"
      role="radiogroup"
      aria-label="Conversation language"
    >
      {UI_VOICE_LANGUAGES.map((lang) => {
        const selected = value === lang;
        return (
          <button
            key={lang}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(lang)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition disabled:opacity-50 ${
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
