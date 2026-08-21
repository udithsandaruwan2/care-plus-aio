import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import type { Message, MessageThread } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { useMessageSocket } from '../messaging/useMessageSocket';
import { Link, Navigate } from 'react-router-dom';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { CacheSourceBadge } from '../lib/query/CacheSourceBadge';
import { queryKeys, STALE_MS } from '../lib/query/keys';
import { readQuery, writeQuery } from '../lib/query/queryClient';
import { useCachedQuery } from '../lib/query/useCachedQuery';
import { useOutboxStore } from '../lib/outbox/outboxStore';

const POLL_MS = 4000;

function formatTime(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

export function MessagesPage() {
  const { user } = useAuth();
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastIdRef = useRef(0);

  const isPatient = user?.role === 'patient';
  const isCaregiver = user?.role === 'caregiver';
  const enabled = Boolean(user?.id && (isPatient || isCaregiver));
  const pendingMessages = useOutboxStore((s) =>
    s.items.filter(
      (i) =>
        i.kind === 'message' &&
        (i.status === 'pending' || i.status === 'sending' || i.status === 'failed'),
    ),
  );

  const threadQuery = useCachedQuery<MessageThread | null>({
    key: enabled ? queryKeys.messageThread(user!.id) : null,
    staleTimeMs: STALE_MS.messageThread,
    enabled,
    fetcher: async () => {
      try {
        return await api.currentMessageThread();
      } catch {
        return null;
      }
    },
  });

  const thread = threadQuery.data;
  const messagesKey = thread ? queryKeys.messages(thread.id) : null;

  const messagesQuery = useCachedQuery<Message[]>({
    key: messagesKey,
    staleTimeMs: STALE_MS.messages,
    enabled: Boolean(thread),
    fetcher: async () => {
      if (!thread) return [];
      return api.listMessages(thread.id, { limit: 100 });
    },
  });

  const messages = messagesQuery.data ?? [];
  const loading =
    (threadQuery.loading && !threadQuery.data) ||
    (Boolean(thread) && messagesQuery.loading && !messagesQuery.data);
  const error = sendError || threadQuery.error || messagesQuery.error;

  useEffect(() => {
    lastIdRef.current = messages[messages.length - 1]?.id ?? 0;
  }, [messages]);

  const mergeMessages = useCallback(
    async (incoming: Message[]) => {
      if (!incoming.length || !messagesKey) return;
      const existing = (await readQuery<Message[]>(messagesKey))?.data ?? [];
      const map = new Map(existing.map((m) => [m.id, m]));
      for (const m of incoming) map.set(m.id, m);
      const merged = [...map.values()].sort((a, b) => a.id - b.id);
      lastIdRef.current = merged[merged.length - 1]?.id ?? lastIdRef.current;
      await writeQuery(messagesKey, merged);
    },
    [messagesKey],
  );

  const markRead = useCallback((threadId: number, lastId: number) => {
    if (lastId <= 0) return;
    void api.markMessagesRead(threadId, lastId).catch(() => undefined);
  }, []);

  useMessageSocket(thread?.id ?? null, {
    onConnected: () => setWsConnected(true),
    onDisconnected: () => setWsConnected(false),
    onMessage: (msg) => {
      void mergeMessages([msg]);
      if (!msg.is_mine && thread) markRead(thread.id, msg.id);
    },
    onRead: (payload) => {
      void (async () => {
        if (!messagesKey) return;
        const existing = (await readQuery<Message[]>(messagesKey))?.data ?? [];
        const next = existing.map((m) =>
          m.is_mine && m.id <= payload.last_read_message_id && m.read_at == null
            ? { ...m, read_at: new Date().toISOString() }
            : m,
        );
        await writeQuery(messagesKey, next);
      })();
    },
  });

  useEffect(() => {
    if (!thread || wsConnected) return;
    const id = window.setInterval(() => {
      void api
        .listMessages(thread.id, { after_id: lastIdRef.current || undefined, limit: 100 })
        .then((rows) => mergeMessages(rows))
        .catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [thread, wsConnected, mergeMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  useEffect(() => {
    if (!thread || messages.length === 0) return;
    const lastFromOther = [...messages].reverse().find((m) => !m.is_mine);
    if (lastFromOther && lastFromOther.read_at == null) {
      markRead(thread.id, lastFromOther.id);
    }
  }, [thread, messages, markRead]);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!thread || !body.trim()) return;
    setSending(true);
    setSendError(null);
    const text = body.trim();
    try {
      const { enqueueMessage } = await import('../lib/outbox/flush');
      const outcome = await enqueueMessage(thread.id, text);
      if (outcome.queued) {
        setBody('');
        setSendError(null);
      } else {
        await mergeMessages([outcome.result]);
        setBody('');
      }
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Could not send message.');
    } finally {
      setSending(false);
    }
  }

  if (user && !isPatient && !isCaregiver) {
    return <Navigate to="/hub" replace />;
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          eyebrow="Messaging"
          title={thread?.partner_label ?? 'Care chat'}
          subtitle={
            thread
              ? wsConnected
                ? 'Connected: messages arrive in realtime.'
                : 'Realtime unavailable: polling for new messages.'
              : 'Start care with a linked partner to unlock messaging.'
          }
        />
        <CacheSourceBadge
          fromCache={threadQuery.fromCache || messagesQuery.fromCache}
          stale={threadQuery.stale || messagesQuery.stale}
        />
      </div>

      {error && (
        <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {loading && <p className="mt-8 text-sm text-muted">Loading conversation…</p>}

      {!loading && !thread && (
        <div className="mt-8 rounded-2xl border border-hair bg-panel shadow-[var(--cp-shadow-soft)] p-5">
          <p className="text-sm text-muted">
            Messaging opens after a care link is active — accept a request, then complete checkout
            (LKR).
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/caregivers">
              <Button>Browse caregivers</Button>
            </Link>
            <Link to="/requests">
              <Button tone="ghost">Open requests</Button>
            </Link>
          </div>
        </div>
      )}

      {thread && (
        <>
          <div className="mt-6 flex min-h-[320px] flex-1 flex-col rounded-2xl border border-hair bg-panel/70 p-4 backdrop-blur-md">
            <ul className="flex-1 space-y-3 overflow-y-auto pr-1">
              {messages.length === 0 && (
                <li className="text-center text-sm text-muted">
                  No messages yet. Introduce yourself to start the care chat.
                </li>
              )}
              {messages.map((msg) => (
                <li
                  key={msg.id}
                  className={`flex ${msg.is_mine ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                      msg.is_mine ? 'bg-cyan/20 text-mist' : 'border border-hair bg-soft text-mist'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.body}</p>
                    <p className="mt-1 text-[10px] text-muted">
                      {formatTime(msg.created_at)}
                      {msg.is_mine && (
                        <span className="ml-2">{msg.read_at ? '· Read' : '· Sent'}</span>
                      )}
                    </p>
                  </div>
                </li>
              ))}
              {pendingMessages
                .filter((i) => Number(i.payload.thread_id) === thread.id)
                .map((item) => (
                  <li key={item.id} className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl border border-amber/40 bg-amber/10 px-4 py-2 text-sm text-mist">
                      <p className="whitespace-pre-wrap">{String(item.payload.body ?? '')}</p>
                      <p className="mt-1 text-[10px] text-amber-200/90">
                        {item.status === 'failed'
                          ? item.error || 'Failed'
                          : item.status === 'sending'
                            ? 'Sending…'
                            : 'Pending · will send when online'}
                      </p>
                    </div>
                  </li>
                ))}
              <div ref={bottomRef} />
            </ul>

            <form
              onSubmit={(e) => void onSend(e)}
              className="mt-4 flex gap-2 border-t border-hair pt-4"
            >
              <input
                className="flex-1 rounded-lg border border-hair bg-panel px-3 py-2 text-sm text-mist outline-none ring-cyan focus:ring-1"
                placeholder="Type a message…"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                maxLength={4000}
              />
              <button
                type="submit"
                disabled={sending || !body.trim()}
                className="rounded-lg bg-cyan px-4 py-2 text-sm font-medium text-inverse disabled:opacity-50"
              >
                {sending ? '…' : 'Send'}
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
