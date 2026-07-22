import { useEffect, useRef } from 'react';
import type { Message } from '@care-plus/api-client';
import { getAccessToken } from '../auth/session';

function wsBase(): string {
  const fromEnv = import.meta.env.VITE_WS_BASE_URL as string | undefined;
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}`;
}

type Handlers = {
  onMessage?: (message: Message) => void;
  onRead?: (payload: {
    thread_id: number;
    last_read_message_id: number;
    reader_id: number;
    updated_count: number;
  }) => void;
  onDisconnected?: () => void;
  onConnected?: () => void;
};

/** JWT WebSocket for a message thread; falls back to polling via caller when disconnected. */
export function useMessageSocket(threadId: number | null, handlers: Handlers) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (threadId == null) return;
    const token = getAccessToken();
    if (!token) return;

    const url = `${wsBase()}/ws/messages/${threadId}/?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => handlersRef.current.onConnected?.();

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as {
          type?: string;
          payload?: Message & {
            thread_id?: number;
            last_read_message_id?: number;
            reader_id?: number;
            updated_count?: number;
          };
        };
        if (msg.type === 'message.created' && msg.payload) {
          handlersRef.current.onMessage?.(msg.payload as Message);
        }
        if (msg.type === 'message.read' && msg.payload) {
          handlersRef.current.onRead?.({
            thread_id: msg.payload.thread_id ?? threadId,
            last_read_message_id: msg.payload.last_read_message_id ?? 0,
            reader_id: msg.payload.reader_id ?? 0,
            updated_count: msg.payload.updated_count ?? 0,
          });
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    ws.onclose = () => handlersRef.current.onDisconnected?.();

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [threadId]);
}
