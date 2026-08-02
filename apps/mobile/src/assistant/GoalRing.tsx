import { StyleSheet, Text, View } from 'react-native';
import { GOAL_FIELDS, goalRingProgress, type IntentDraft } from '@care-plus/core';
import { colors } from '@care-plus/ui-tokens';

const LABELS: Record<(typeof GOAL_FIELDS)[number], string> = {
  condition: 'Condition',
  language: 'Language',
  care_level: 'Care level',
};

type Props = {
  intent: IntentDraft;
};

/** Simple segment Goal Ring (Skia arcs deferred — clear fill state for MVP). */
export function GoalRing({ intent }: Props) {
  const progress = goalRingProgress(intent);
  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        {GOAL_FIELDS.map((field) => {
          const filled = Boolean(intent[field]);
          return (
            <View key={field} style={[styles.seg, filled && styles.segFilled]}>
              <Text style={[styles.segText, filled && styles.segTextFilled]}>{LABELS[field]}</Text>
            </View>
          );
        })}
      </View>
      <Text style={styles.pct}>{Math.round(progress * 100)}% goal</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: 'center',
    gap: 8,
  },
  row: {
    flexDirection: 'row',
    gap: 8,
  },
  seg: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.borderHair,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  segFilled: {
    borderColor: colors.accentCyan,
    backgroundColor: 'rgba(34, 211, 238, 0.15)',
  },
  segText: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
  },
  segTextFilled: {
    color: colors.accentCyan,
  },
  pct: {
    color: colors.textMuted,
    fontSize: 12,
  },
});
