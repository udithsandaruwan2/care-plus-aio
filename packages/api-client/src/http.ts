/** HTTP resilience helpers (Step 82) — timeout, backoff retry, typed network errors. */

export class NetworkError extends Error {
  constructor(
    message = 'Network request failed',
    public cause?: unknown,
  ) {
    super(message);
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends NetworkError {
  constructor(
    message = 'Request timed out',
    public timeoutMs?: number,
  ) {
    super(message);
    this.name = 'TimeoutError';
  }
}

export function isNetworkError(err: unknown): err is NetworkError {
  return err instanceof NetworkError;
}

export function isTimeoutError(err: unknown): err is TimeoutError {
  return err instanceof TimeoutError;
}

/** Safe to retry after a transport failure (no response received). */
export function isIdempotentMethod(method: string | undefined): boolean {
  const m = (method || 'GET').toUpperCase();
  return m === 'GET' || m === 'HEAD' || m === 'OPTIONS';
}

export function backoffDelayMs(attempt: number, baseMs = 300): number {
  return baseMs * 2 ** Math.max(0, attempt);
}

export type FetchWithTimeoutOptions = {
  timeoutMs?: number;
  signal?: AbortSignal;
};

/**
 * fetch wrapper that aborts after ``timeoutMs`` and maps transport failures
 * to :class:`NetworkError` / :class:`TimeoutError`.
 */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  opts: FetchWithTimeoutOptions = {},
): Promise<Response> {
  const timeoutMs = opts.timeoutMs ?? 30_000;
  const controller = new AbortController();
  const onParentAbort = () => controller.abort(opts.signal?.reason);
  if (opts.signal) {
    if (opts.signal.aborted) {
      controller.abort(opts.signal.reason);
    } else {
      opts.signal.addEventListener('abort', onParentAbort, { once: true });
    }
  }

  const timer = setTimeout(() => {
    controller.abort(new TimeoutError(`Request timed out after ${timeoutMs}ms`, timeoutMs));
  }, timeoutMs);

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof TimeoutError) throw err;
    if (err instanceof DOMException && err.name === 'AbortError') {
      const reason = controller.signal.reason;
      if (reason instanceof TimeoutError) throw reason;
      if (reason instanceof Error) throw reason;
      throw new TimeoutError(`Request timed out after ${timeoutMs}ms`, timeoutMs);
    }
    throw new NetworkError(err instanceof Error ? err.message : 'Network request failed', err);
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener('abort', onParentAbort);
  }
}

export type RetryOptions = {
  maxRetries?: number;
  baseDelayMs?: number;
  /** When false, never retry (default: retry only idempotent methods). */
  retry?: boolean;
  sleep?: (ms: number) => Promise<void>;
};

async function defaultSleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms));
}

/**
 * Run ``fn`` with bounded retries on network/timeout errors for safe methods.
 */
export async function withRetry<T>(
  method: string | undefined,
  fn: () => Promise<T>,
  opts: RetryOptions = {},
): Promise<T> {
  const maxRetries = opts.maxRetries ?? 2;
  const sleep = opts.sleep ?? defaultSleep;
  const allow = opts.retry ?? isIdempotentMethod(method);
  let attempt = 0;
  for (;;) {
    try {
      return await fn();
    } catch (err) {
      const retryable = isNetworkError(err) || isTimeoutError(err);
      if (!allow || !retryable || attempt >= maxRetries) throw err;
      await sleep(backoffDelayMs(attempt, opts.baseDelayMs));
      attempt += 1;
    }
  }
}
