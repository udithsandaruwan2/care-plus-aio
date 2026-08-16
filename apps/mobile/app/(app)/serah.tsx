import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Redirect } from 'expo-router';
import { AssistantState, STATE_COPY } from '@care-plus/core';
import { colors } from '@care-plus/ui-tokens';
import { useAuth } from '../../src/auth/AuthContext';
import { usePatientProfile } from '../../src/auth/usePatientProfile';
import { NeuralCoreSkia } from '../../src/neural-core/NeuralCoreSkia';
import { EntityChips } from '../../src/assistant/EntityChips';
import { GoalRing } from '../../src/assistant/GoalRing';
import { MatchResultCards } from '../../src/assistant/MatchResultCards';
import { useAssistant } from '../../src/assistant/store';
import { useVoiceTurn } from '../../src/assistant/useVoiceTurn';
import type { UiVoiceLanguage } from '../../src/assistant/uiVoiceLanguage';

const LANGS: UiVoiceLanguage[] = ['English', 'Sinhala', 'Tamil'];

export default function SerahScreen() {
  const { user } = useAuth();
  const { canRequestCare, completionPercent } = usePatientProfile();
  const state = useAssistant((s) => s.state);
  const intent = useAssistant((s) => s.intent);
  const chat = useAssistant((s) => s.chat);
  const match = useAssistant((s) => s.match);
  const matching = useAssistant((s) => s.matching);
  const uiLanguage = useAssistant((s) => s.uiLanguage);
  const setUiLanguage = useAssistant((s) => s.setUiLanguage);
  const reset = useAssistant((s) => s.reset);
  const { runTurn, busy, error, consentNeeded, grantConsent } = useVoiceTurn();
  const [text, setText] = useState('');

  if (!user) return <Redirect href="/(auth)/login" />;
  if (user.role !== 'patient') {
    return (
      <View style={styles.screen}>
        <Text style={styles.title}>Serah is for patients</Text>
        <Text style={styles.muted}>Caregiver and admin flows stay on the web for now.</Text>
      </View>
    );
  }

  async function onSend() {
    const line = text.trim();
    if (!line || busy) return;
    setText('');
    await runTurn(line);
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={80}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.eyebrow}>SERAH NEURAL CORE</Text>
        <Text style={styles.title}>Talk with Serah</Text>
        <Text style={styles.subtitle}>
          {STATE_COPY[state]}
          {user.role === 'patient' ? ` · profile ${completionPercent}%` : ''}
        </Text>

        <View style={styles.langRow}>
          {LANGS.map((lang) => (
            <Pressable
              key={lang}
              onPress={() => setUiLanguage(lang)}
              style={[styles.langChip, uiLanguage === lang && styles.langChipActive]}
            >
              <Text style={[styles.langText, uiLanguage === lang && styles.langTextActive]}>
                {lang === 'English' ? 'EN' : lang === 'Sinhala' ? 'සිං' : 'த'}
              </Text>
            </Pressable>
          ))}
          <Pressable onPress={() => reset()} style={styles.reset}>
            <Text style={styles.resetText}>New</Text>
          </Pressable>
        </View>

        <NeuralCoreSkia
          state={state}
          amplitude={
            state === AssistantState.LISTENING || state === AssistantState.THINKING ? 0.7 : 0.25
          }
        />
        <GoalRing intent={intent} />
        <EntityChips intent={intent} />

        {error ? <Text style={styles.error}>{error}</Text> : null}
        {consentNeeded ? (
          <Pressable
            onPress={() => void grantConsent()}
            style={({ pressed }) => [styles.consentBtn, pressed && styles.pressed]}
          >
            <Text style={styles.consentText}>Grant AI processing consent</Text>
          </Pressable>
        ) : null}

        <View style={styles.chat}>
          {chat.length === 0 ? (
            <Text style={styles.muted}>
              Type in Sinhala, Tamil, or English — e.g. “මට දියවැඩියාව තියෙනවා, Colombo area”.
            </Text>
          ) : (
            chat.map((m) => (
              <View
                key={m.id}
                style={[styles.bubble, m.role === 'user' ? styles.bubbleUser : styles.bubbleSerah]}
              >
                <Text style={styles.bubbleRole}>{m.role === 'user' ? 'You' : 'Serah'}</Text>
                <Text style={styles.bubbleText}>{m.text}</Text>
              </View>
            ))
          )}
        </View>

        {matching && !match?.results?.length ? (
          <View style={styles.searchPanel}>
            <Text style={styles.searchTitle}>Finding caregivers…</Text>
            <View style={styles.searchTrack}>
              <View style={styles.searchFill} />
            </View>
            <Text style={styles.muted}>You can keep chatting while Serah ranks matches.</Text>
            <View style={styles.skeleton} />
            <View style={styles.skeleton} />
            <View style={styles.skeleton} />
          </View>
        ) : null}

        {match?.results?.length ? (
          <MatchResultCards match={match} canRequestCare={canRequestCare} uiLanguage={uiLanguage} />
        ) : null}
      </ScrollView>

      <View style={styles.composer}>
        <TextInput
          style={styles.input}
          placeholder="Message Serah…"
          placeholderTextColor={colors.textMuted}
          value={text}
          onChangeText={setText}
          editable={!busy}
          onSubmitEditing={() => void onSend()}
          returnKeyType="send"
        />
        <Pressable
          onPress={() => void onSend()}
          disabled={busy || !text.trim()}
          style={({ pressed }) => [
            styles.send,
            (busy || !text.trim()) && styles.sendDisabled,
            pressed && styles.pressed,
          ]}
        >
          {busy ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.sendText}>Send</Text>}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bgVoid,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 24,
    gap: 12,
  },
  eyebrow: {
    color: colors.accentCyan,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.textPrimary,
    fontSize: 26,
    fontWeight: '700',
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    marginBottom: 4,
  },
  muted: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  langRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  langChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.borderHair,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  langChipActive: {
    borderColor: colors.accentCyan,
    backgroundColor: 'rgba(13, 148, 136, 0.12)',
  },
  langText: {
    color: colors.textMuted,
    fontWeight: '600',
    fontSize: 12,
  },
  langTextActive: {
    color: colors.accentCyan,
  },
  reset: {
    marginLeft: 'auto',
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  resetText: {
    color: colors.accentAmber,
    fontWeight: '600',
    fontSize: 12,
  },
  error: {
    color: colors.accentRose,
    fontSize: 13,
  },
  consentBtn: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    backgroundColor: colors.accentViolet,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  consentText: {
    color: colors.textPrimary,
    fontWeight: '700',
    fontSize: 13,
  },
  chat: {
    gap: 8,
    minHeight: 80,
  },
  bubble: {
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.borderHair,
  },
  bubbleUser: {
    alignSelf: 'flex-end',
    backgroundColor: 'rgba(13, 148, 136, 0.12)',
    maxWidth: '88%',
  },
  bubbleSerah: {
    alignSelf: 'flex-start',
    backgroundColor: colors.bgPanel,
    maxWidth: '88%',
  },
  bubbleRole: {
    color: colors.textMuted,
    fontSize: 10,
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  bubbleText: {
    color: colors.textPrimary,
    fontSize: 14,
    lineHeight: 20,
  },
  searchPanel: {
    gap: 10,
    marginTop: 8,
  },
  searchTitle: {
    color: colors.accentCyan,
    fontSize: 13,
    fontWeight: '700',
  },
  searchTrack: {
    height: 6,
    overflow: 'hidden',
    borderRadius: 999,
    backgroundColor: 'rgba(13, 148, 136, 0.16)',
  },
  searchFill: {
    width: '55%',
    height: 6,
    borderRadius: 999,
    backgroundColor: colors.accentMint,
  },
  skeleton: {
    height: 88,
    borderRadius: 16,
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.borderHair,
    opacity: 0.7,
  },
  composer: {
    flexDirection: 'row',
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.borderHair,
    backgroundColor: colors.bgVoid,
  },
  input: {
    flex: 1,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: colors.bgPanel,
    color: colors.textPrimary,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
  send: {
    borderRadius: 14,
    backgroundColor: colors.accentCyan,
    paddingHorizontal: 16,
    justifyContent: 'center',
    minWidth: 72,
    alignItems: 'center',
  },
  sendDisabled: {
    opacity: 0.4,
  },
  sendText: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.85,
  },
});
