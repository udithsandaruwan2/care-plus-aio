import type { IntentDraft } from '@care-plus/core';

type ChipDef = {
  key: keyof IntentDraft;
  label: string;
  className: string;
};

const CHIPS: ChipDef[] = [
  { key: 'condition', label: 'Condition', className: 'border-cyan/50 text-cyan' },
  { key: 'language', label: 'Language', className: 'border-violet/50 text-violet' },
  { key: 'care_level', label: 'Care level', className: 'border-mint/50 text-mint' },
  { key: 'urgency', label: 'Urgency', className: 'border-amber/50 text-amber' },
];

/** Color-coded chips that pop in as intent fields are captured. */
export function EntityChips({ intent }: { intent: IntentDraft }) {
  const languageLabel =
    intent.languages && intent.languages.length > 1
      ? intent.languages.join(' + ')
      : intent.language;

  const values: Partial<Record<keyof IntentDraft, string | undefined>> = {
    condition: intent.condition,
    language: languageLabel,
    care_level: intent.care_level,
    urgency: intent.urgency,
  };

  const active = CHIPS.filter((c) => values[c.key]);
  if (active.length === 0) {
    return <p className="text-xs text-muted">No details captured yet.</p>;
  }
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {active.map((c) => (
        <span
          key={c.key}
          className={`animate-[fadeIn_260ms_ease] rounded-full border bg-void/40 px-3 py-1 text-xs ${c.className}`}
        >
          <span className="opacity-60">{c.label}:</span> {values[c.key]}
        </span>
      ))}
    </div>
  );
}
