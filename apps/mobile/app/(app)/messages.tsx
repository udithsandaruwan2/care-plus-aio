import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Redirect } from 'expo-router';
import type { Message, MessageThread } from '@care-plus/api-client';
import { ApiError } from '@care-plus/api-client';
import { colors } from '@care-plus/ui-tokens';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth/AuthContext';

const POLL_MS = 4000;

export default function MessagesScreen() {
  const { user } = useAuth();
  const [thread, setThread] = useState<MessageThread | null | undefined>(undefined);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const listRef = useRef<FlatList<Message>>(null);
  const lastIdRef = useRef(0);

  const loadThread = useCallback(async () => {
    try {
      const t = await api.currentMessageThread();
      setThread(t);
      return t;
    } catch (err) {
      setThread(null);
      setError(err instanceof Error ? err.message : 'Could not load messages');
      return null;
    }
  }, []);

  const loadMessages = useCallback(async (threadId: number, afterId?: number) => {
    try {
      const batch = await api.listMessages(threadId, {
        after_id: afterId,
        limit: 50,
      });
      if (!afterId) {
        setMessages(batch);
        lastIdRef.current = batch.length ? batch[batch.length - 1].id : 0;
      } else if (batch.length) {
        setMessages((prev) => {
          const ids = new Set(prev.map((m) => m.id));
          const next = [...prev];
          for (const m of batch) {
            if (!ids.has(m.id)) next.push(m);
          }
          return next;
        });
        lastIdRef.current = batch[batch.length - 1].id;
      }
      if (batch.length) {
        const last = batch[batch.length - 1];
        if (!last.is_mine) {
          void api.markMessagesRead(threadId, last.id).catch(() => undefined);
        }
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError('Thread not found');
      }
    }
  }, []);

  useEffect(() => {
    if (!user || (user.role !== 'patient' && user.role !== 'caregiver')) return;
    let cancelled = false;
    void (async () => {
      const t = await loadThread();
      if (cancelled || !t) return;
      await loadMessages(t.id);
    })();
    return () => {
      cancelled = true;
    };
  }, [user, loadThread, loadMessages]);

  useEffect(() => {
    if (!thread?.id) return;
    const id = setInterval(() => {
      void loadMessages(thread.id, lastIdRef.current || undefined);
    }, POLL_MS);
    return () => clearInterval(id);
  }, [thread?.id, loadMessages]);

  if (!user) return <Redirect href="/(auth)/login" />;

  if (user.role !== 'patient' && user.role !== 'caregiver') {
    return (
      <View style={styles.center}>
        <Text style={styles.title}>Messages</Text>
        <Text style={styles.muted}>Messaging is for patients and caregivers with an active care link.</Text>
      </View>
    );
  }

  if (thread === undefined) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accentCyan} />
      </View>
    );
  }

  if (!thread) {
    return (
      <View style={styles.center}>
        <Text style={styles.title}>Messages</Text>
        <Text style={styles.muted}>
          No active care link yet. When a request is accepted and care starts, chat with your partner
          here.
        </Text>
        <Pressable onPress={() => void loadThread()} style={styles.refresh}>
          <Text style={styles.refreshText}>Check again</Text>
        </Pressable>
      </View>
    );
  }

  async function onSend() {
    const body = text.trim();
    if (!body || !thread || sending) return;
    setSending(true);
    setError(null);
    try {
      const msg = await api.sendMessage(thread.id, body);
      setMessages((prev) => [...prev, msg]);
      lastIdRef.current = msg.id;
      setText('');
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send');
    } finally {
      setSending(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={80}
    >
      <View style={styles.header}>
        <Text style={styles.title}>{thread.partner_label || 'Care partner'}</Text>
        {thread.unread_count > 0 ? (
          <Text style={styles.unread}>{thread.unread_count} unread</Text>
        ) : (
          <Text style={styles.muted}>Secure care chat</Text>
        )}
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={styles.list}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
        ListEmptyComponent={<Text style={styles.muted}>No messages yet — say hello.</Text>}
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.is_mine ? styles.mine : styles.theirs]}>
            <Text style={styles.bubbleMeta}>{item.is_mine ? 'You' : item.sender_role}</Text>
            <Text style={styles.bubbleText}>{item.body}</Text>
          </View>
        )}
      />

      <View style={styles.composer}>
        <TextInput
          style={styles.input}
          placeholder="Write a message…"
          placeholderTextColor={colors.textMuted}
          value={text}
          onChangeText={setText}
          editable={!sending}
          onSubmitEditing={() => void onSend()}
          returnKeyType="send"
        />
        <Pressable
          onPress={() => void onSend()}
          disabled={sending || !text.trim()}
          style={[styles.send, (sending || !text.trim()) && styles.disabled]}
        >
          {sending ? (
            <ActivityIndicator color={colors.bgVoid} />
          ) : (
            <Text style={styles.sendText}>Send</Text>
          )}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bgVoid },
  center: {
    flex: 1,
    backgroundColor: colors.bgVoid,
    padding: 24,
    justifyContent: 'center',
    gap: 12,
  },
  header: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 8, gap: 2 },
  title: { color: colors.textPrimary, fontSize: 20, fontWeight: '700' },
  muted: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  unread: { color: colors.accentAmber, fontSize: 12, fontWeight: '600' },
  error: { color: colors.accentRose, paddingHorizontal: 20, fontSize: 13 },
  list: { paddingHorizontal: 16, paddingVertical: 12, gap: 8, flexGrow: 1 },
  bubble: {
    borderRadius: 14,
    padding: 12,
    marginBottom: 8,
    maxWidth: '86%',
    borderWidth: 1,
    borderColor: colors.borderHair,
  },
  mine: {
    alignSelf: 'flex-end',
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
  },
  theirs: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(18, 22, 34, 0.9)',
  },
  bubbleMeta: {
    color: colors.textMuted,
    fontSize: 10,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  bubbleText: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  composer: {
    flexDirection: 'row',
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.borderHair,
  },
  input: {
    flex: 1,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderHair,
    backgroundColor: 'rgba(18, 22, 34, 0.9)',
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
  sendText: { color: colors.bgVoid, fontWeight: '700' },
  disabled: { opacity: 0.4 },
  refresh: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(34,211,238,0.4)',
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  refreshText: { color: colors.accentCyan, fontWeight: '600', fontSize: 13 },
});
