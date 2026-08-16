import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import type { MatchHit, MatchResponse } from '@care-plus/api-client';
import { ApiError } from '@care-plus/api-client';
import { colors } from '@care-plus/ui-tokens';
import { api } from '../api';
import { useAssistant } from './store';
import type { UiVoiceLanguage } from './uiVoiceLanguage';

function FactorBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <View style={styles.factorRow}>
      <Text style={styles.factorLabel}>{label}</Text>
      <View style={styles.factorTrack}>
        <View style={[styles.factorFill, { width: `${pct}%`, backgroundColor: color }]} />
      </View>
      <Text style={styles.factorPct}>{pct}</Text>
    </View>
  );
}

function MatchCard({
  hit,
  canRequestCare,
  matchRunId,
  uiLanguage,
}: {
  hit: MatchHit;
  canRequestCare: boolean;
  matchRunId: number;
  uiLanguage: UiVoiceLanguage;
}) {
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const km =
    hit.distance_m != null && Number.isFinite(hit.distance_m)
      ? `${(hit.distance_m / 1000).toFixed(1)} km`
      : null;
  const unavailable = hit.is_available === false;

  function startRequest() {
    if (!canRequestCare) {
      setFormError('Complete your patient profile (at least 80%) before requesting care.');
      return;
    }
    if (sent || busy || unavailable) return;
    setFormError(null);
    setShowForm(true);
  }

  async function onRequest() {
    if (!canRequestCare || sent || busy || unavailable) return;
    setBusy(true);
    setFormError(null);
    try {
      await api.createCareRequest({
        caregiver_id: hit.caregiver_id,
        message: message.trim() || undefined,
        match_run_id: matchRunId,
        match_snapshot: {
          rank: hit.rank,
          score: hit.score,
          breakdown: hit.breakdown,
          explanation: hit.explanation,
          distance_m: hit.distance_m ?? null,
        },
      });
      setSent(true);
      setShowForm(false);
      const confirmation =
        uiLanguage === 'Sinhala'
          ? `${hit.display_name || 'මෙම caregiver'} වෙත ඉල්ලීම යැව්වා.`
          : uiLanguage === 'Tamil'
            ? `${hit.display_name || 'இந்த பராமரிப்பாளர்'}-க்கு கோரிக்கை அனுப்பப்பட்டது.`
            : `Request sent to ${hit.display_name || 'this caregiver'} (pending).`;
      useAssistant.getState().appendChat({ role: 'serah', text: confirmation, route: 'ACTION' });
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string } | null;
        setFormError(
          typeof body?.detail === 'string' ? body.detail : `Request failed (${err.status})`,
        );
      } else {
        setFormError(err instanceof Error ? err.message : 'Could not send request.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[styles.card, unavailable && styles.cardMuted]}>
      <View style={styles.header}>
        <Text style={styles.rank}>#{hit.rank}</Text>
        <View style={styles.headerMain}>
          <Text style={styles.name}>{hit.display_name || `Caregiver ${hit.caregiver_id}`}</Text>
          <Text style={styles.meta}>
            score {hit.score.toFixed(2)}
            {km ? ` · ${km}` : ''}
            {unavailable ? ' · unavailable' : ''}
          </Text>
        </View>
      </View>

      {(hit.specialties?.length || hit.languages?.length) && (
        <Text style={styles.tags} numberOfLines={2}>
          {[...(hit.specialties ?? []).slice(0, 3), ...(hit.languages ?? []).slice(0, 2)].join(
            ' · ',
          )}
        </Text>
      )}

      <View style={styles.bars}>
        <FactorBar label="CBF" value={hit.breakdown.cbf} color={colors.accentCyan} />
        <FactorBar label="CF" value={hit.breakdown.cf} color={colors.accentViolet} />
        <FactorBar label="Geo" value={hit.breakdown.geo} color={colors.accentMint} />
        <FactorBar label="Trust" value={hit.breakdown.trust} color={colors.accentAmber} />
      </View>

      <Text style={styles.xai} numberOfLines={3}>
        {hit.explanation}
      </Text>

      {formError ? <Text style={styles.error}>{formError}</Text> : null}

      {showForm && !sent ? (
        <View style={styles.form}>
          <TextInput
            style={styles.input}
            placeholder="Optional message to caregiver"
            placeholderTextColor={colors.textMuted}
            value={message}
            onChangeText={setMessage}
            editable={!busy}
          />
          <View style={styles.formRow}>
            <Pressable onPress={() => setShowForm(false)} style={styles.secondaryBtn}>
              <Text style={styles.secondaryText}>Cancel</Text>
            </Pressable>
            <Pressable
              onPress={() => void onRequest()}
              disabled={busy}
              style={[styles.primaryBtn, busy && styles.disabled]}
            >
              {busy ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.primaryText}>Send request</Text>
              )}
            </Pressable>
          </View>
        </View>
      ) : (
        <Pressable
          onPress={startRequest}
          disabled={sent || unavailable}
          style={[
            styles.primaryBtn,
            (sent || unavailable || !canRequestCare) && styles.disabled,
            sent && styles.sentBtn,
          ]}
        >
          <Text style={[styles.primaryText, sent && styles.sentText]}>
            {sent ? 'Request sent · pending' : unavailable ? 'Unavailable' : 'Request caregiver'}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

type Props = {
  match: MatchResponse;
  canRequestCare?: boolean;
  uiLanguage?: UiVoiceLanguage;
};

export function MatchResultCards({ match, canRequestCare = true, uiLanguage = 'English' }: Props) {
  if (!match.results?.length) return null;

  return (
    <View style={styles.wrap}>
      <Text style={styles.section}>
        Matches · {match.latency_ms} ms
        {match.emergency ? ' · emergency' : ''}
      </Text>
      {!canRequestCare ? (
        <Text style={styles.gate}>
          Complete your patient profile (≥ 80%) before requesting care.
        </Text>
      ) : null}
      {match.results.slice(0, 8).map((hit) => (
        <MatchCard
          key={hit.caregiver_id}
          hit={hit}
          canRequestCare={canRequestCare}
          matchRunId={match.request_id}
          uiLanguage={uiLanguage}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: 10,
    marginTop: 8,
  },
  section: {
    color: colors.textPrimary,
    fontWeight: '700',
    fontSize: 15,
  },
  gate: {
    color: colors.accentAmber,
    fontSize: 12,
    lineHeight: 17,
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: colors.bgPanel,
    padding: 14,
    gap: 8,
  },
  cardMuted: {
    opacity: 0.65,
  },
  header: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
  },
  rank: {
    color: colors.accentMint,
    fontWeight: '800',
    fontSize: 16,
    fontVariant: ['tabular-nums'],
  },
  headerMain: {
    flex: 1,
    gap: 2,
  },
  name: {
    color: colors.textPrimary,
    fontWeight: '700',
    fontSize: 15,
  },
  meta: {
    color: colors.textMuted,
    fontSize: 12,
  },
  tags: {
    color: colors.accentViolet,
    fontSize: 12,
  },
  bars: {
    gap: 4,
  },
  factorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  factorLabel: {
    width: 36,
    color: colors.textMuted,
    fontSize: 10,
  },
  factorTrack: {
    flex: 1,
    height: 6,
    borderRadius: 999,
    backgroundColor: 'rgba(5, 6, 10, 0.7)',
    overflow: 'hidden',
  },
  factorFill: {
    height: '100%',
    borderRadius: 999,
  },
  factorPct: {
    width: 24,
    textAlign: 'right',
    color: colors.textMuted,
    fontSize: 10,
    fontVariant: ['tabular-nums'],
  },
  xai: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 17,
  },
  error: {
    color: colors.accentRose,
    fontSize: 12,
  },
  form: {
    gap: 8,
  },
  formRow: {
    flexDirection: 'row',
    gap: 8,
  },
  input: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: 'rgba(5, 6, 10, 0.6)',
    color: colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  primaryBtn: {
    marginTop: 2,
    borderRadius: 999,
    backgroundColor: colors.accentCyan,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignItems: 'center',
    flex: 1,
  },
  primaryText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  secondaryBtn: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.borderHair,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignItems: 'center',
  },
  secondaryText: {
    color: colors.textMuted,
    fontWeight: '600',
    fontSize: 13,
  },
  disabled: {
    opacity: 0.45,
  },
  sentBtn: {
    backgroundColor: 'rgba(52, 211, 153, 0.2)',
    borderWidth: 1,
    borderColor: colors.accentMint,
  },
  sentText: {
    color: colors.accentMint,
  },
});
