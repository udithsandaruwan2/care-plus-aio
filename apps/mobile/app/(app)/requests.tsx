import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Redirect } from 'expo-router';
import type { CareRequest } from '@care-plus/api-client';
import { colors } from '@care-plus/ui-tokens';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth/AuthContext';

export default function RequestsScreen() {
  const { user } = useAuth();
  const [items, setItems] = useState<CareRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} tintColor={colors.accentCyan} />}
    >
      <Text style={styles.title}>{user.role === 'caregiver' ? 'Inbox' : 'Care requests'}</Text>
      <Text style={styles.subtitle}>Pull to refresh. Accept/reject for caregivers lands in Step 66.</Text>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !items.length ? <ActivityIndicator color={colors.accentCyan} /> : null}

      {!loading && !items.length ? (
        <Text style={styles.empty}>No care requests yet. Ask Serah for a match, then tap Request caregiver.</Text>
      ) : null}

      {items.map((r) => (
        <View key={r.id} style={styles.card}>
          <Text style={styles.status}>{r.status}</Text>
          <Text style={styles.name}>
            {user.role === 'caregiver' ? r.patient_email : r.caregiver_name || `Caregiver #${r.caregiver_id}`}
          </Text>
          {r.message ? <Text style={styles.msg}>{r.message}</Text> : null}
          <Text style={styles.meta}>#{r.id} · expires {r.expires_at?.slice?.(0, 10) || '—'}</Text>
        </View>
      ))}

      <Pressable onPress={() => void load()} style={styles.refresh}>
        <Text style={styles.refreshText}>Refresh</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bgVoid },
  content: { padding: 20, gap: 12, paddingBottom: 40 },
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '700' },
  subtitle: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  error: { color: colors.accentRose, fontSize: 13 },
  empty: { color: colors.textMuted, fontSize: 14, lineHeight: 20 },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: 'rgba(18, 22, 34, 0.9)',
    padding: 14,
    gap: 4,
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
  meta: { color: colors.textMuted, fontSize: 11, marginTop: 4 },
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
