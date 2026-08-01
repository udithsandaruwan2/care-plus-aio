import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';
import { brand, colors } from '@care-plus/ui-tokens';
import { t } from '@care-plus/core';
import { api, apiBaseUrl } from '../src/api';

type HealthState =
  | { status: 'loading' }
  | { status: 'ok'; detail: string }
  | { status: 'error'; message: string };

export default function HomeScreen() {
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
      <Stack.Screen options={{ title: brand.name, headerShown: false }} />

      <View style={styles.hero}>
        <View style={styles.dot} />
        <Text style={styles.brand}>{brand.name}</Text>
        <Text style={styles.tagline}>{t('en', 'app.tagline')}</Text>
        <Text style={styles.theme}>{brand.theme} · Expo mobile</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Shared packages</Text>
        <Text style={styles.cardBody}>
          Wired to @care-plus/core, @care-plus/api-client, and @care-plus/ui-tokens — same contracts
          as the web app.
        </Text>
        <Text style={styles.mono}>API {apiBaseUrl}</Text>

        {health.status === 'loading' && (
          <View style={styles.row}>
            <ActivityIndicator color={colors.accentCyan} />
            <Text style={styles.muted}>Checking /api/v1/health/…</Text>
          </View>
        )}
        {health.status === 'ok' && (
          <Text style={styles.ok}>API healthy · {health.detail}</Text>
        )}
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

      <Text style={styles.footer}>Step 62 bootstrap · auth & Neural Core land in 63–64</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bgVoid,
    paddingHorizontal: 24,
    paddingTop: 72,
    paddingBottom: 32,
  },
  hero: {
    marginBottom: 28,
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.accentCyan,
    marginBottom: 14,
  },
  brand: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  tagline: {
    marginTop: 10,
    color: colors.textMuted,
    fontSize: 16,
    lineHeight: 22,
  },
  theme: {
    marginTop: 8,
    color: colors.accentViolet,
    fontSize: 13,
  },
  card: {
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: 'rgba(18, 22, 34, 0.85)',
    padding: 18,
    gap: 10,
  },
  cardTitle: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: '600',
  },
  cardBody: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
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
  footer: {
    marginTop: 'auto',
    color: colors.textMuted,
    fontSize: 12,
  },
});
