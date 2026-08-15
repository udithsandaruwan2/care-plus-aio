import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Link, Redirect, router } from 'expo-router';
import { ApiError, userNeedsOtp } from '@care-plus/api-client';
import { brand, colors } from '@care-plus/ui-tokens';
import { t } from '@care-plus/core';
import { useAuth } from '../../src/auth/AuthContext';

type Role = 'patient' | 'caregiver';

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: string; email?: string[] } | null;
    if (typeof body?.detail === 'string') return body.detail;
    if (body?.email?.[0]) return body.email[0];
    return `Request failed (${err.status}).`;
  }
  return 'Something went wrong. Try again.';
}

export default function RegisterScreen() {
  const { user, loading, register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<Role>('patient');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && user) {
    if (userNeedsOtp(user)) return <Redirect href="/(auth)/otp" />;
    return <Redirect href="/(app)" />;
  }

  async function onSubmit() {
    setError(null);
    setBusy(true);
    try {
      const me = await register(email.trim(), password, role);
      if (userNeedsOtp(me)) {
        router.replace('/(auth)/otp');
        return;
      }
      router.replace('/(app)');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.eyebrow}>{brand.name}</Text>
      <Text style={styles.title}>Create account</Text>
      <Text style={styles.subtitle}>
        Join as a patient seeking care or a caregiver offering services in Sri Lanka.
      </Text>

      <View style={styles.roleRow}>
        {(['patient', 'caregiver'] as const).map((r) => (
          <Pressable
            key={r}
            onPress={() => setRole(r)}
            style={[styles.roleChip, role === r && styles.roleChipActive]}
          >
            <Text style={[styles.roleText, role === r && styles.roleTextActive]}>
              {r === 'patient' ? 'Patient' : 'Caregiver'}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>{t('en', 'login.email')}</Text>
        <TextInput
          style={styles.input}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          placeholder="you@example.com"
          placeholderTextColor={colors.textMuted}
          value={email}
          onChangeText={setEmail}
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>{t('en', 'login.password')}</Text>
        <TextInput
          style={styles.input}
          secureTextEntry
          autoComplete="new-password"
          placeholder="Min. 8 characters"
          placeholderTextColor={colors.textMuted}
          value={password}
          onChangeText={setPassword}
        />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable
        onPress={() => void onSubmit()}
        disabled={busy || !email.trim() || password.length < 8}
        style={({ pressed }) => [
          styles.button,
          (busy || !email.trim() || password.length < 8) && styles.buttonDisabled,
          pressed && styles.buttonPressed,
        ]}
      >
        {busy ? (
          <ActivityIndicator color={colors.bgVoid} />
        ) : (
          <Text style={styles.buttonText}>Create account</Text>
        )}
      </Pressable>

      <Text style={styles.footer}>
        Already have an account?{' '}
        <Link href="/(auth)/login" style={styles.link}>
          {t('en', 'action.signIn')}
        </Link>
      </Text>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bgVoid,
    paddingHorizontal: 24,
    paddingTop: 24,
  },
  eyebrow: {
    color: colors.accentCyan,
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  title: {
    marginTop: 8,
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: '700',
  },
  subtitle: {
    marginTop: 8,
    marginBottom: 20,
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  roleRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 18,
  },
  roleChip: {
    flex: 1,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderHair,
    paddingVertical: 12,
    alignItems: 'center',
  },
  roleChipActive: {
    borderColor: colors.accentCyan,
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
  },
  roleText: {
    color: colors.textMuted,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  roleTextActive: {
    color: colors.accentCyan,
  },
  field: {
    marginBottom: 14,
    gap: 6,
  },
  label: {
    color: colors.textMuted,
    fontSize: 11,
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  input: {
    borderWidth: 1,
    borderColor: colors.borderHair,
    borderRadius: 12,
    backgroundColor: 'rgba(18, 22, 34, 0.85)',
    color: colors.textPrimary,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
  },
  error: {
    color: colors.accentRose,
    marginBottom: 12,
    fontSize: 13,
  },
  button: {
    marginTop: 8,
    borderRadius: 999,
    backgroundColor: colors.accentCyan,
    paddingVertical: 14,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonPressed: {
    opacity: 0.85,
  },
  buttonText: {
    color: colors.bgVoid,
    fontWeight: '700',
    fontSize: 15,
  },
  footer: {
    marginTop: 20,
    color: colors.textMuted,
    fontSize: 14,
  },
  link: {
    color: colors.accentCyan,
    fontWeight: '600',
  },
});
