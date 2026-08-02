import { StyleSheet, Text, View } from 'react-native';
import type { IntentDraft } from '@care-plus/core';
import { colors } from '@care-plus/ui-tokens';

type Props = {
  intent: IntentDraft;
};

const CHIP_COLOR: Record<string, string> = {
  condition: colors.accentCyan,
  language: colors.accentViolet,
  care_level: colors.accentMint,
  urgency: colors.accentAmber,
};

export function EntityChips({ intent }: Props) {
  const chips: { key: string; label: string; value: string }[] = [];
  if (intent.condition) chips.push({ key: 'condition', label: 'Condition', value: intent.condition });
  if (intent.language) chips.push({ key: 'language', label: 'Language', value: intent.language });
  if (intent.languages?.length && intent.languages.length > 1) {
    chips.push({ key: 'languages', label: 'Languages', value: intent.languages.join(', ') });
  }
  if (intent.care_level) chips.push({ key: 'care_level', label: 'Care', value: intent.care_level });
  if (intent.urgency) chips.push({ key: 'urgency', label: 'Urgency', value: intent.urgency });

  if (!chips.length) return null;

  return (
    <View style={styles.wrap}>
      {chips.map((c) => (
        <View
          key={c.key}
          style={[styles.chip, { borderColor: CHIP_COLOR[c.key] ?? colors.borderHair }]}
        >
          <Text style={styles.label}>{c.label}</Text>
          <Text style={[styles.value, { color: CHIP_COLOR[c.key] ?? colors.textPrimary }]}>
            {c.value}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    borderRadius: 12,
    borderWidth: 1,
    backgroundColor: 'rgba(18, 22, 34, 0.85)',
    paddingHorizontal: 10,
    paddingVertical: 8,
    minWidth: 96,
  },
  label: {
    color: colors.textMuted,
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  value: {
    marginTop: 2,
    fontSize: 13,
    fontWeight: '600',
  },
});
