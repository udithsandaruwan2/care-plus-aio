import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
} from 'react-native';
import { Redirect, router } from 'expo-router';
import { ApiError, userNeedsOtp } from '@care-plus/api-client';
import { colors } from '@care-plus/ui-tokens';
import { useAuth } from '../../src/auth/AuthContext';

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: string } | null;
    if (typeof body?.detail === 'string') return body.detail;
    return `Request failed (${err.status}).`;
  }
  return 'Something went wrong. Try again.';
}

export default function OtpScreen() {
  const { user, loading, requestOtp, verifyOtp } = useAuth();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const requested = useRef(false);

  useEffect(() => {
    if (!userNeedsOtp(user) || requested.current) return;
    requested.current = true;
    void requestOtp()
      .then((res) => setInfo(res.detail || 'A verification code was sent to your email.'))
      .catch((err) => setError(errorMessage(err)));
  }, [user, requestOtp]);

  if (!loading && !user) {
    return <Redirect href="/(auth)/login" />;
  }
  if (!loading && user && !userNeedsOtp(user)) {
    return <Redirect href="/(app)" />;
  }

  async function onSubmit() {
    setError(null);
    setBusy(true);
    try {
      await verifyOtp(code.trim());
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
      <Text style={styles.title}>Verify your email</Text>
      <Text style={styles.subtitle}>
        Enter the 6-digit code we sent you before hire, payment, or medical records.
      </Text>
      {info ? <Text style={styles.info}>{info}</Text> : null}
      <TextInput
        style={styles.input}
        keyboardType="number-pad"
        maxLength={6}
        value={code}
        onChangeText={(v) => setCode(v.replace(/\D/g, '').slice(0, 6))}
        placeholder="000000"
        placeholderTextColor={colors.textMuted}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <Pressable
        onPress={() => void onSubmit()}
        disabled={busy || code.length !== 6}
        style={({ pressed }) => [styles.button, pressed && styles.pressed]}
      >
        {busy ? (
          <ActivityIndicator color={colors.bgVoid} />
        ) : (
          <Text style={styles.buttonText}>Verify</Text>
        )}
      </Pressable>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, padding: 24, justifyContent: 'center', backgroundColor: colors.bgVoid },
  title: { color: colors.textPrimary, fontSize: 22, fontWeight: '600' },
  subtitle: { color: colors.textMuted, marginTop: 8, marginBottom: 16 },
  info: { color: colors.accentMint, marginBottom: 12 },
  input: {
    borderWidth: 1,
    borderColor: colors.borderHair,
    borderRadius: 12,
    padding: 12,
    color: colors.textPrimary,
    letterSpacing: 8,
    fontSize: 20,
  },
  error: { color: colors.accentRose, marginTop: 8 },
  button: {
    marginTop: 16,
    backgroundColor: colors.accentCyan,
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  pressed: { opacity: 0.85 },
  buttonText: { color: colors.bgVoid, fontWeight: '600' },
});
