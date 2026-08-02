import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@care-plus/ui-tokens';
import { api, apiBaseUrl } from '../../src/api';

type HealthState =
  | { status: 'loading' }
  | { status: 'ok'; detail: string }
  | { status: 'error'; message: string };

/** Dev/status screen — keeps the Step 62 health check accessible after auth. */
export default function StatusScreen() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' });

  async function checkHealth() {
    setHealth({ status: 'loading' });
    try {
      const res = await api.health();
      setHealth({
        status: 'ok',
        detail: `${res.status} · db ${res.db} · redis ${res.redis}`,
      });
    } catch (err) {
      setHealth({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not reach API',
      });
    }
  }

  useEffect(() => {
    void checkHealth();
  }, []);

  return (
    <View style={styles.screen}>
      <Text style={styles.mono}>API {apiBaseUrl}</Text>

      {health.status === 'loading' && (
        <View style={styles.row}>
          <ActivityIndicator color={colors.accentCyan} />
          <Text style={styles.muted}>Checking /api/v1/health/…</Text>
        </View>
      )}
      {health.status === 'ok' && <Text style={styles.ok}>API healthy · {health.detail}</Text>}
      {health.status === 'error' && (
        <Text style={styles.error}>
          Offline — start Docker backend on :8000. {health.message}
        </Text>
      )}

      <Pressable
        onPress={() => void checkHealth()}
        style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
      >
        <Text style={styles.buttonText}>Retry health check</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bgVoid,
    padding: 24,
    gap: 12,
  },
  mono: {
    color: colors.accentMint,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  muted: {
    color: colors.textMuted,
    fontSize: 13,
  },
  ok: {
    color: colors.accentMint,
    fontSize: 14,
  },
  error: {
    color: colors.accentRose,
    fontSize: 13,
    lineHeight: 18,
  },
  button: {
    marginTop: 6,
    alignSelf: 'flex-start',
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(34, 211, 238, 0.45)',
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  buttonPressed: {
    opacity: 0.8,
  },
  buttonText: {
    color: colors.accentCyan,
    fontSize: 13,
    fontWeight: '600',
  },
});
