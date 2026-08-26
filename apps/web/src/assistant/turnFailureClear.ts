/** Lets the match WebSocket clear a stale HTTP timeout banner when a reply arrives. */

type Clearer = () => void;

let clearer: Clearer | null = null;

export function bindTurnFailureClearer(fn: Clearer): () => void {
  clearer = fn;
  return () => {
    if (clearer === fn) clearer = null;
  };
}

export function clearTurnFailureFromStream(): void {
  clearer?.();
}
