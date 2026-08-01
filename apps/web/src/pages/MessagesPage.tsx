import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import type { Message, MessageThread } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { useMessageSocket } from '../messaging/useMessageSocket';
import { Link, Navigate } from 'react-router-dom';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';

const POLL_MS = 4000;

function formatTime(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

export function MessagesPage() {
  const { user } = useAuth();
  const [thread, setThread] = useState<MessageThread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastIdRef = useRef(0);

  const isPatient = user?.role === 'patient';
  const isCaregiver = user?.role === 'caregiver';

  const mergeMessages = useCallback((incoming: Message[]) => {
    if (!incoming.length) return;
    setMessages((prev) => {
      const map = new Map(prev.map((m) => [m.id, m]));
      for (const m of incoming) map.set(m.id, m);
      const merged = [...map.values()].sort((a, b) => a.id - b.id);
      lastIdRef.current = merged[merged.length - 1]?.id ?? lastIdRef.current;
      return merged;
    });
  }, []);

  const loadThread = useCallback(() => {
    setLoading(true);
    setError(null);
    return api
      .currentMessageThread()
      .then((t) => {
        setThread(t);
        return t;
      })
      .catch((err) => {
        setThread(null);
        setError(err instanceof Error ? err.message : 'Could not load conversation.');
        return null;
      })
      .finally(() => setLoading(false));
  }, []);

  const loadMessages = useCallback((threadId: number, afterId = 0) => {
    return api
      .listMessages(threadId, { after_id: afterId || undefined, limit: 100 })
      .then((rows) => mergeMessages(rows))
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Could not load messages.');
      });
  }, [mergeMessages]);

  const markRead = useCallback((threadId: number, lastId: number) => {
    if (lastId <= 0) return;
    void api.markMessagesRead(threadId, lastId).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!isPatient && !isCaregiver) {
      setLoading(false);
      return;
    }
    void loadThread().then((t) => {
      if (t) void loadMessages(t.id);
    });
  }, [isPatient, isCaregiver, loadThread, loadMessages]);

  useMessageSocket(thread?.id ?? null, {
    onConnected: () => setWsConnected(true),
    onDisconnected: () => setWsConnected(false),
    onMessage: (msg) => {
      mergeMessages([msg]);
      if (!msg.is_mine && thread) markRead(thread.id, msg.id);
    },
    onRead: (payload) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.is_mine && m.id <= payload.last_read_message_id && m.read_at == null
            ? { ...m, read_at: new Date().toISOString() }
            : m,
        ),
      );
    },
  });

  useEffect(() => {
    if (!thread || wsConnected) return;
    const id = window.setInterval(() => {
      void loadMessages(thread.id, lastIdRef.current);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [thread, wsConnected, loadMessages]);

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
    setError(null);
    try {
      const sent = await api.sendMessage(thread.id, body.trim());
      mergeMessages([sent]);
      setBody('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send message.');
    } finally {
      setSending(false);
    }
  }

  if (user && !isPatient && !isCaregiver) {
    return <Navigate to="/platform" replace />;
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
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

        {error && (
          <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        {loading && <p className="mt-8 text-sm text-muted">Loading conversation…</p>}

        {!loading && !thread && (
          <div className="mt-8 rounded-2xl border border-hair bg-panel/50 p-5">
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
                        msg.is_mine
                          ? 'bg-cyan/20 text-mist'
                          : 'border border-hair bg-void/40 text-mist'
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.body}</p>
                      <p className="mt-1 text-[10px] text-muted">
                        {formatTime(msg.created_at)}
                        {msg.is_mine && (
                          <span className="ml-2">
                            {msg.read_at ? '· Read' : '· Sent'}
                          </span>
                        )}
                      </p>
                    </div>
                  </li>
                ))}
                <div ref={bottomRef} />
              </ul>

              <form onSubmit={(e) => void onSend(e)} className="mt-4 flex gap-2 border-t border-hair pt-4">
                <input
                  className="flex-1 rounded-lg border border-hair bg-void/60 px-3 py-2 text-sm text-mist outline-none ring-cyan focus:ring-1"
                  placeholder="Type a message…"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  maxLength={4000}
                />
                <button
                  type="submit"
                  disabled={sending || !body.trim()}
                  className="rounded-lg bg-cyan px-4 py-2 text-sm font-medium text-void disabled:opacity-50"
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
