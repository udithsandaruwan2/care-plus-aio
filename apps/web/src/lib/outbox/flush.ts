import { ApiError, isNetworkError, isTimeoutError } from '@care-plus/api-client';
import type { CareRequestCreate } from '@care-plus/api-client';
import { api } from '../../auth/api';
import {
  type OutboxItem,
  outboxDelete,
  outboxGet,
  outboxList,
  outboxPut,
} from './idbOutbox';
import { useOutboxStore } from './outboxStore';

const SYNC_TAG = 'careplus-outbox';

/** HTTP statuses that must not be retried forever (validation / policy). */
export const PERMANENT_HTTP = new Set([400, 403, 404, 409, 422, 451]);

export function isPermanentFailure(err: unknown): boolean {
  return err instanceof ApiError && PERMANENT_HTTP.has(err.status);
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `ob-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.body && typeof err.body === 'object' && err.body !== null && 'detail' in err.body) {
      return String((err.body as { detail: unknown }).detail);
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return 'Request failed.';
}

async function refreshStore(): Promise<void> {
  await useOutboxStore.getState().refresh();
}

export async function registerOutboxSync(): Promise<void> {
  try {
    if (!('serviceWorker' in navigator)) return;
    const reg = await navigator.serviceWorker.ready;
    const syncManager = (
      reg as ServiceWorkerRegistration & {
        sync?: { register: (tag: string) => Promise<void> };
      }
    ).sync;
    if (syncManager?.register) {
      await syncManager.register(SYNC_TAG);
    }
  } catch {
    /* Background Sync unsupported — online listener still flushes */
  }
}

async function deliver(item: OutboxItem): Promise<void> {
  const key = item.id;
  if (item.kind === 'care_request') {
    await api.createCareRequest({
      ...(item.payload as CareRequestCreate),
      idempotency_key: key,
    });
    return;
  }
  if (item.kind === 'message') {
    const threadId = Number(item.payload.thread_id);
    const body = String(item.payload.body ?? '');
    await api.sendMessage(threadId, body, key);
    return;
  }
  if (item.kind === 'payment_confirm') {
    const providerIntentId = String(item.payload.provider_intent_id ?? '');
    await api.confirmMockPayment(providerIntentId, key);
  }
}

export async function flushOne(item: OutboxItem): Promise<void> {
  const sending: OutboxItem = {
    ...item,
    status: 'sending',
    updatedAt: Date.now(),
  };
  await outboxPut(sending);
  await refreshStore();
  try {
    await deliver(item);
    await outboxDelete(item.id);
    await refreshStore();
  } catch (err) {
    if (isPermanentFailure(err)) {
      await outboxPut({
        ...item,
        status: 'failed',
        permanent: true,
        error: errorMessage(err),
        updatedAt: Date.now(),
      });
      await refreshStore();
      throw err;
    }
    if (isNetworkError(err) || isTimeoutError(err) || !navigator.onLine) {
      await outboxPut({
        ...item,
        status: 'pending',
        error: undefined,
        updatedAt: Date.now(),
      });
      await refreshStore();
      await registerOutboxSync();
      throw err;
    }
    // Other HTTP (5xx) — keep pending for retry
    if (err instanceof ApiError && err.status >= 500) {
      await outboxPut({
        ...item,
        status: 'pending',
        error: errorMessage(err),
        updatedAt: Date.now(),
      });
      await refreshStore();
      throw err;
    }
    await outboxPut({
      ...item,
      status: 'failed',
      permanent: isPermanentFailure(err),
      error: errorMessage(err),
      updatedAt: Date.now(),
    });
    await refreshStore();
    throw err;
  }
}

let flushInFlight: Promise<void> | null = null;

export async function flushOutbox(): Promise<void> {
  if (flushInFlight) return flushInFlight;
  flushInFlight = (async () => {
    const items = await outboxList();
    for (const item of items) {
      if (item.status === 'failed' && item.permanent) continue;
      if (typeof navigator !== 'undefined' && !navigator.onLine) break;
      try {
        await flushOne(item);
      } catch (err) {
        if (typeof navigator !== 'undefined' && !navigator.onLine) break;
        if (isNetworkError(err) || isTimeoutError(err)) break;
        /* permanent / other — continue with remaining items */
      }
    }
  })().finally(() => {
    flushInFlight = null;
  });
  return flushInFlight;
}

export type EnqueueResult<T> =
  | { queued: false; result: T }
  | { queued: true; item: OutboxItem };

async function enqueueAndMaybeSend(
  kind: OutboxItem['kind'],
  payload: Record<string, unknown>,
  label: string,
  sendNow: (key: string) => Promise<unknown>,
): Promise<EnqueueResult<unknown>> {
  const id = String(payload.idempotency_key || newIdempotencyKey());
  const now = Date.now();
  const item: OutboxItem = {
    id,
    kind,
    payload: { ...payload, idempotency_key: id },
    status: 'pending',
    label,
    createdAt: now,
    updatedAt: now,
  };
  await outboxPut(item);
  await refreshStore();

  if (typeof navigator !== 'undefined' && navigator.onLine) {
    try {
      const result = await sendNow(id);
      await outboxDelete(id);
      await refreshStore();
      return { queued: false, result };
    } catch (err) {
      if (isPermanentFailure(err)) {
        await outboxPut({
          ...item,
          status: 'failed',
          permanent: true,
          error: errorMessage(err),
          updatedAt: Date.now(),
        });
        await refreshStore();
        throw err;
      }
      if (isNetworkError(err) || isTimeoutError(err)) {
        await registerOutboxSync();
        return { queued: true, item };
      }
      // 5xx etc. — leave pending
      await outboxPut({
        ...item,
        status: 'pending',
        error: errorMessage(err),
        updatedAt: Date.now(),
      });
      await refreshStore();
      await registerOutboxSync();
      return { queued: true, item };
    }
  }

  await registerOutboxSync();
  return { queued: true, item };
}

export async function enqueueCareRequest(
  input: CareRequestCreate,
  label?: string,
): Promise<EnqueueResult<Awaited<ReturnType<typeof api.createCareRequest>>>> {
  const key = input.idempotency_key || newIdempotencyKey();
  return enqueueAndMaybeSend(
    'care_request',
    { ...input, idempotency_key: key },
    label || `Care request #${input.caregiver_id}`,
    (id) => api.createCareRequest({ ...input, idempotency_key: id }),
  ) as Promise<EnqueueResult<Awaited<ReturnType<typeof api.createCareRequest>>>>;
}

export async function enqueueMessage(
  threadId: number,
  body: string,
): Promise<EnqueueResult<Awaited<ReturnType<typeof api.sendMessage>>>> {
  const key = newIdempotencyKey();
  return enqueueAndMaybeSend(
    'message',
    { thread_id: threadId, body, idempotency_key: key },
    `Message to thread ${threadId}`,
    (id) => api.sendMessage(threadId, body, id),
  ) as Promise<EnqueueResult<Awaited<ReturnType<typeof api.sendMessage>>>>;
}

export async function enqueuePaymentConfirm(
  providerIntentId: string,
): Promise<EnqueueResult<Awaited<ReturnType<typeof api.confirmMockPayment>>>> {
  const key = newIdempotencyKey();
  return enqueueAndMaybeSend(
    'payment_confirm',
    { provider_intent_id: providerIntentId, idempotency_key: key },
    `Confirm payment ${providerIntentId}`,
    (id) => api.confirmMockPayment(providerIntentId, id),
  ) as Promise<EnqueueResult<Awaited<ReturnType<typeof api.confirmMockPayment>>>>;
}

export async function dismissFailedOutbox(id: string): Promise<void> {
  await outboxDelete(id);
  await refreshStore();
}

export async function retryOutboxItem(id: string): Promise<void> {
  const item = await outboxGet(id);
  if (!item) return;
  if (item.permanent) return;
  await flushOne({ ...item, status: 'pending', error: undefined });
}

/** Wire online + SW sync messages once. */
export function bindOutboxLifecycle(): () => void {
  void useOutboxStore.getState().refresh();
  void flushOutbox();

  const onOnline = () => {
    void flushOutbox();
  };
  window.addEventListener('online', onOnline);

  const onSwMessage = (event: MessageEvent) => {
    const data = event.data;
    if (data && typeof data === 'object' && (data as { type?: string }).type === 'careplus-outbox-flush') {
      void flushOutbox();
    }
  };
  navigator.serviceWorker?.addEventListener('message', onSwMessage);

  return () => {
    window.removeEventListener('online', onOnline);
    navigator.serviceWorker?.removeEventListener('message', onSwMessage);
  };
}
