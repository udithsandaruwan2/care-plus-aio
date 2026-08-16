import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Redirect } from 'expo-router';
import type { CareRequest } from '@care-plus/api-client';
import { ApiError } from '@care-plus/api-client';
import { colors } from '@care-plus/ui-tokens';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth/AuthContext';

function actionError(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: string } | null;
    if (typeof body?.detail === 'string') return body.detail;
    return `Request failed (${err.status})`;
  }
  return err instanceof Error ? err.message : 'Something went wrong';
}

export default function RequestsScreen() {
  const { user } = useAuth();
  const [items, setItems] = useState<CareRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectFor, setRejectFor] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.listCareRequests(1);
      setItems(res.results ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load requests');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) return <Redirect href="/(auth)/login" />;

  if (user.role !== 'patient' && user.role !== 'caregiver') {
    return (
      <View style={styles.screenPad}>
        <Text style={styles.title}>Requests</Text>
        <Text style={styles.subtitle}>Inbox actions are for patients and caregivers.</Text>
      </View>
    );
  }

  async function patchRow(id: number, fn: () => Promise<CareRequest>) {
    setBusyId(id);
    setError(null);
    try {
      const updated = await fn();
      setItems((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setRejectFor(null);
      setRejectReason('');
    } catch (err) {
      setError(actionError(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={loading}
          onRefresh={() => void load()}
          tintColor={colors.accentCyan}
        />
      }
    >
      <Text style={styles.title}>{user.role === 'caregiver' ? 'Inbox' : 'Care requests'}</Text>
      <Text style={styles.subtitle}>
        {user.role === 'caregiver'
          ? 'Accept or reject pending patient requests.'
          : 'Cancel pending requests you sent. Messaging opens after a care link is active.'}
      </Text>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !items.length ? <ActivityIndicator color={colors.accentCyan} /> : null}

      {!loading && !items.length ? (
        <Text style={styles.empty}>
          No care requests yet.
          {user.role === 'patient'
            ? ' Ask Serah for a match, then tap Request caregiver.'
            : ' Waiting for patients to request you.'}
        </Text>
      ) : null}

      {items.map((r) => {
        const busy = busyId === r.id;
        const pending = r.status === 'pending';
        return (
          <View key={r.id} style={styles.card}>
            <Text style={styles.status}>{r.status}</Text>
            <Text style={styles.name}>
              {user.role === 'caregiver'
                ? r.patient_email
                : r.caregiver_name || `Caregiver #${r.caregiver_id}`}
            </Text>
            {r.message ? <Text style={styles.msg}>{r.message}</Text> : null}
            <Text style={styles.meta}>
              #{r.id} · expires {r.expires_at?.slice?.(0, 10) || '—'}
              {r.relationship_status ? ` · ${r.relationship_status}` : ''}
            </Text>

            {pending && user.role === 'caregiver' ? (
              <View style={styles.actions}>
                <Pressable
                  disabled={busy}
                  onPress={() => void patchRow(r.id, () => api.acceptCareRequest(r.id))}
                  style={[styles.acceptBtn, busy && styles.disabled]}
                >
                  {busy && rejectFor !== r.id ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.acceptText}>Accept</Text>
                  )}
                </Pressable>
                <Pressable
                  disabled={busy}
                  onPress={() => {
                    setRejectFor(r.id);
                    setRejectReason('');
                  }}
                  style={[styles.rejectBtn, busy && styles.disabled]}
                >
                  <Text style={styles.rejectText}>Reject</Text>
                </Pressable>
              </View>
            ) : null}

            {pending && user.role === 'patient' ? (
              <Pressable
                disabled={busy}
                onPress={() => void patchRow(r.id, () => api.cancelCareRequest(r.id))}
                style={[styles.cancelBtn, busy && styles.disabled]}
              >
                {busy ? (
                  <ActivityIndicator color={colors.accentRose} />
                ) : (
                  <Text style={styles.cancelText}>Cancel request</Text>
                )}
              </Pressable>
            ) : null}

            {rejectFor === r.id ? (
              <View style={styles.rejectForm}>
                <TextInput
                  style={styles.input}
                  placeholder="Optional reason"
                  placeholderTextColor={colors.textMuted}
                  value={rejectReason}
                  onChangeText={setRejectReason}
                  editable={!busy}
                />
                <View style={styles.actions}>
                  <Pressable
                    onPress={() => setRejectFor(null)}
                    style={styles.secondaryBtn}
                    disabled={busy}
                  >
                    <Text style={styles.secondaryText}>Back</Text>
                  </Pressable>
                  <Pressable
                    disabled={busy}
                    onPress={() =>
                      void patchRow(r.id, () => api.rejectCareRequest(r.id, rejectReason.trim()))
                    }
                    style={[styles.rejectBtn, busy && styles.disabled]}
                  >
                    {busy ? (
                      <ActivityIndicator color={colors.accentRose} />
                    ) : (
                      <Text style={styles.rejectText}>Confirm reject</Text>
                    )}
                  </Pressable>
                </View>
              </View>
            ) : null}
          </View>
        );
      })}

      <Pressable onPress={() => void load()} style={styles.refresh}>
        <Text style={styles.refreshText}>Refresh</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bgVoid },
  screenPad: { flex: 1, backgroundColor: colors.bgVoid, padding: 20 },
  content: { padding: 20, gap: 12, paddingBottom: 40 },
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '700' },
  subtitle: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  error: { color: colors.accentRose, fontSize: 13 },
  empty: { color: colors.textMuted, fontSize: 14, lineHeight: 20 },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: colors.bgPanel,
    padding: 14,
    gap: 6,
  },
  status: {
    color: colors.accentCyan,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  name: { color: colors.textPrimary, fontWeight: '600', fontSize: 15 },
  msg: { color: colors.textMuted, fontSize: 13 },
  meta: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
  actions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  acceptBtn: {
    flex: 1,
    borderRadius: 999,
    backgroundColor: colors.accentMint,
    paddingVertical: 10,
    alignItems: 'center',
  },
  acceptText: { color: '#FFFFFF', fontWeight: '700', fontSize: 13 },
  rejectBtn: {
    flex: 1,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(251,113,133,0.5)',
    paddingVertical: 10,
    alignItems: 'center',
  },
  rejectText: { color: colors.accentRose, fontWeight: '700', fontSize: 13 },
  cancelBtn: {
    marginTop: 8,
    alignSelf: 'flex-start',
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(251,113,133,0.45)',
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  cancelText: { color: colors.accentRose, fontWeight: '600', fontSize: 13 },
  rejectForm: { gap: 8, marginTop: 8 },
  input: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: colors.bgPanel,
    color: colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  secondaryBtn: {
    flex: 1,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.borderHair,
    paddingVertical: 10,
    alignItems: 'center',
  },
  secondaryText: { color: colors.textMuted, fontWeight: '600', fontSize: 13 },
  disabled: { opacity: 0.5 },
  refresh: {
    alignSelf: 'flex-start',
    marginTop: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(34,211,238,0.4)',
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  refreshText: { color: colors.accentCyan, fontWeight: '600', fontSize: 13 },
});
