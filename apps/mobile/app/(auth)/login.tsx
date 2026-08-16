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

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: string; email?: string[] } | null;
    if (typeof body?.detail === 'string') return body.detail;
    if (body?.email?.[0]) return body.email[0];
    if (err.status === 401) return 'Invalid email or password.';
    return `Request failed (${err.status}).`;
  }
  return 'Something went wrong. Try again.';
}

export default function LoginScreen() {
  const { user, loading, login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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
      const me = await login(email.trim(), password);
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
      <Text style={styles.eyebrow}>{t('en', 'login.eyebrow')}</Text>
      <Text style={styles.title}>{t('en', 'login.title')}</Text>
      <Text style={styles.subtitle}>{t('en', 'login.subtitle')}</Text>

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
          autoComplete="password"
          placeholder="••••••••"
          placeholderTextColor={colors.textMuted}
          value={password}
          onChangeText={setPassword}
        />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable
        onPress={() => void onSubmit()}
        disabled={busy || !email.trim() || !password}
        style={({ pressed }) => [
          styles.button,
          (busy || !email.trim() || !password) && styles.buttonDisabled,
          pressed && styles.buttonPressed,
        ]}
      >
        {busy ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.buttonText}>{t('en', 'action.signIn')}</Text>
        )}
      </Pressable>

      <Text style={styles.footer}>
        {t('en', 'login.noAccount')}{' '}
        <Link href="/(auth)/register" style={styles.link}>
          {t('en', 'action.createAccount')}
        </Link>
      </Text>

      <Text style={styles.brand}>{brand.name}</Text>
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
    marginBottom: 24,
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
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
    backgroundColor: colors.bgPanel,
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
    color: '#FFFFFF',
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
  brand: {
    marginTop: 'auto',
    marginBottom: 28,
    color: colors.textMuted,
    fontSize: 12,
  },
});
