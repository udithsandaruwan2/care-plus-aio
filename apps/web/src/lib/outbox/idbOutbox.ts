/** IndexedDB outbox for queued writes (Step 95). */

const DB_NAME = 'careplus-outbox';
const DB_VERSION = 1;
const STORE = 'items';

export type OutboxKind = 'care_request' | 'message' | 'payment_confirm';

export type OutboxStatus = 'pending' | 'sending' | 'failed';

export type OutboxItem = {
  id: string;
  kind: OutboxKind;
  /** Request payload (includes idempotency_key). */
  payload: Record<string, unknown>;
  status: OutboxStatus;
  error?: string;
  /** Permanent HTTP failure — do not retry. */
  permanent?: boolean;
  label?: string;
  createdAt: number;
  updatedAt: number;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('indexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error ?? new Error('outbox idb open failed'));
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
  });
}

export async function outboxPut(item: OutboxItem): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error('outbox put failed'));
      tx.objectStore(STORE).put(item);
    });
  } catch {
    /* private mode */
  }
}

export async function outboxGet(id: string): Promise<OutboxItem | null> {
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).get(id);
      req.onerror = () => reject(req.error ?? new Error('outbox get failed'));
      req.onsuccess = () => resolve((req.result as OutboxItem | undefined) ?? null);
    });
  } catch {
    return null;
  }
}

export async function outboxDelete(id: string): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error('outbox delete failed'));
      tx.objectStore(STORE).delete(id);
    });
  } catch {
    /* ignore */
  }
}

export async function outboxList(): Promise<OutboxItem[]> {
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).getAll();
      req.onerror = () => reject(req.error ?? new Error('outbox list failed'));
      req.onsuccess = () => {
        const rows = (req.result as OutboxItem[]) ?? [];
        rows.sort((a, b) => a.createdAt - b.createdAt);
        resolve(rows);
      };
    });
  } catch {
    return [];
  }
}
