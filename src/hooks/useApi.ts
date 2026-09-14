import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../lib/api';

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  /** True when the engine answered 503: warming up, not broken. */
  pending: boolean;
  loading: boolean;
  reload: () => void;
}

/**
 * Fetch once on mount, optionally re-fetch on an interval, and expose the
 * three states the UI actually has to draw: loading, warming-up, and failed.
 *
 * Results are dropped if the component unmounted first, so a slow response
 * cannot set state on a dead component.
 */
export function useApi<T>(fetcher: () => Promise<T>, intervalMs?: number): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const alive = useRef(true);
  // Held in a ref so an inline arrow function as `fetcher` does not restart
  // the effect on every render.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    alive.current = true;

    const run = async () => {
      try {
        const result = await fetcherRef.current();
        if (!alive.current) return;
        setData(result);
        setError(null);
        setPending(false);
      } catch (caught) {
        if (!alive.current) return;
        const isPending = caught instanceof ApiError && caught.pending;
        setPending(isPending);
        setError(caught instanceof Error ? caught.message : 'Request failed');
      } finally {
        if (alive.current) setLoading(false);
      }
    };

    run();

    let timer: ReturnType<typeof setInterval> | undefined;
    if (intervalMs && intervalMs > 0) timer = setInterval(run, intervalMs);

    return () => {
      alive.current = false;
      if (timer) clearInterval(timer);
    };
  }, [intervalMs, nonce]);

  return { data, error, pending, loading, reload };
}
