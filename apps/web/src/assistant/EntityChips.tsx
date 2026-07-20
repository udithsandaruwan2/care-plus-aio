import type { IntentDraft } from '@care-plus/core';
import { chipLabels, localizeCareLevel } from './locale';
import type { UiVoiceLanguage } from './uiVoiceLanguage';

type ChipDef = {
  key: keyof IntentDraft;
  labelKey: 'condition' | 'language' | 'care_level' | 'urgency';
  className: string;
};

const CHIPS: ChipDef[] = [
  { key: 'condition', labelKey: 'condition', className: 'border-cyan/50 text-cyan' },
  { key: 'language', labelKey: 'language', className: 'border-violet/50 text-violet' },
  { key: 'care_level', labelKey: 'care_level', className: 'border-mint/50 text-mint' },
  { key: 'urgency', labelKey: 'urgency', className: 'border-amber/50 text-amber' },
];

/** Color-coded chips that pop in as intent fields are captured. */
export function EntityChips({
  intent,
  uiLanguage = 'English',
}: {
  intent: IntentDraft;
  uiLanguage?: UiVoiceLanguage;
}) {
  const labels = chipLabels(uiLanguage);
  const languageLabel =
    intent.languages && intent.languages.length > 1
      ? intent.languages.join(' + ')
      : intent.language;

  const values: Partial<Record<keyof IntentDraft, string | undefined>> = {
    condition: intent.condition,
    language: languageLabel,
    care_level: localizeCareLevel(intent.care_level, uiLanguage),
    urgency: intent.urgency,
  };

  const active = CHIPS.filter((c) => values[c.key]);
  if (active.length === 0) {
    return <p className="text-xs text-muted">{labels.empty}</p>;
  }
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {active.map((c) => (
        <span
          key={c.key}
          className={`animate-[fadeIn_260ms_ease] rounded-full border bg-void/40 px-3 py-1 text-xs ${c.className}`}
        >
          <span className="opacity-60">{labels[c.labelKey]}:</span> {values[c.key]}
        </span>
      ))}
    </div>
  );
}
