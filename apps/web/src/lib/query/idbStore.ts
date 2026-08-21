/** Minimal IndexedDB key/value store for offline query persistence (Step 94). */

const DB_NAME = 'careplus-query-cache';
const DB_VERSION = 1;
const STORE = 'entries';

export type IdbEntry = {
  key: string;
  data: unknown;
  updatedAt: number;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('indexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error ?? new Error('idb open failed'));
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
  });
}

export async function idbGet(key: string): Promise<IdbEntry | null> {
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).get(key);
      req.onerror = () => reject(req.error ?? new Error('idb get failed'));
      req.onsuccess = () => resolve((req.result as IdbEntry | undefined) ?? null);
    });
  } catch {
    return null;
  }
}

export async function idbSet(entry: IdbEntry): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error('idb set failed'));
      tx.objectStore(STORE).put(entry);
    });
  } catch {
    /* offline / private mode — memory cache still works */
  }
}

export async function idbDelete(key: string): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error('idb delete failed'));
      tx.objectStore(STORE).delete(key);
    });
  } catch {
    /* ignore */
  }
}

export async function idbClear(): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error('idb clear failed'));
      tx.objectStore(STORE).clear();
    });
  } catch {
    /* ignore */
  }
}
