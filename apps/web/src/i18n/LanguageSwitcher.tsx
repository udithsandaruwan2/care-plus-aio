import { LOCALES, type Locale } from '@care-plus/core';
import { useLocale } from './LocaleProvider';

const LABELS: Record<Locale, string> = {
  en: 'EN',
  si: 'සිං',
  ta: 'தமி',
};

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLocale();

  return (
    <div
      className="inline-flex items-center gap-1 rounded-full border border-hair bg-panel px-1 py-1 text-xs shadow-[var(--cp-shadow-soft)]"
      role="group"
      aria-label={t('lang.switcher')}
    >
      {LOCALES.map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => setLocale(code)}
          className={`rounded-full px-2.5 py-1 transition ${
            locale === code
              ? 'bg-elevated text-mist'
              : 'text-muted hover:bg-soft hover:text-mist'
          }`}
          title={code === 'en' ? t('lang.en') : code === 'si' ? t('lang.si') : t('lang.ta')}
          aria-pressed={locale === code}
        >
          {LABELS[code]}
        </button>
      ))}
    </div>
  );
}
