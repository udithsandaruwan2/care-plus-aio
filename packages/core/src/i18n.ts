/** Minimal i18n dictionary stub (en / si / ta). Expand in later steps. */
export type Locale = 'en' | 'si' | 'ta';

const messages = {
  en: {
    'app.tagline': 'Voice-driven caregiver matching',
    'app.ready': 'Ready',
    'assistant.idle': 'Tap to speak',
    'assistant.listening': 'Listening…',
  },
  si: {
    'app.tagline': 'හඬ මගින් රැකවරණය සම්බන්ධ කිරීම',
    'app.ready': 'සූදානම්',
    'assistant.idle': 'කතා කිරීමට තට්ටු කරන්න',
    'assistant.listening': 'සවන් දෙමින්…',
  },
  ta: {
    'app.tagline': 'குரல் வழி பராமரிப்பாளர் பொருத்தம்',
    'app.ready': 'தயார்',
    'assistant.idle': 'பேச தட்டவும்',
    'assistant.listening': 'கேட்கிறது…',
  },
} as const;

export type MessageKey = keyof (typeof messages)['en'];

export function t(locale: Locale, key: MessageKey): string {
  return messages[locale][key] ?? messages.en[key] ?? key;
}
