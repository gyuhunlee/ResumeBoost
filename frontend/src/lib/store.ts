import { useCallback, useEffect, useSyncExternalStore } from "react";

/**
 * Tiny stale-while-revalidate cache for page data.
 *
 * Pages read from here instead of starting with sample data, so:
 *  - the first visit shows a loading skeleton, never stale sample rows;
 *  - switching tabs or reloading shows the last real data instantly
 *    (kept in localStorage per user), then quietly refreshes it.
 */

type Entry<T> = { data: T | null; status: "idle" | "loading" | "ready" | "error"; savedAt: number };

const entries = new Map<string, Entry<unknown>>();
const inflight = new Map<string, Promise<unknown>>();
const listeners = new Set<() => void>();
const PREFIX = "rb:cache:";

const emit = () => listeners.forEach((l) => l());

function read<T>(key: string): Entry<T> {
  let e = entries.get(key) as Entry<T> | undefined;
  if (!e) {
    e = { data: null, status: "idle", savedAt: 0 };
    try {
      const raw = localStorage.getItem(PREFIX + key);
      if (raw) {
        const saved = JSON.parse(raw) as { data: T; savedAt: number };
        e = { data: saved.data, status: "idle", savedAt: saved.savedAt };
      }
    } catch {
      /* storage unavailable or corrupt: start empty */
    }
    entries.set(key, e);
  }
  return e;
}

function write<T>(key: string, next: Entry<T>) {
  entries.set(key, next);
  if (next.status === "ready") {
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify({ data: next.data, savedAt: next.savedAt }));
    } catch {
      /* quota or private mode: memory cache still works */
    }
  }
  emit();
}

/** Fetch `key` (deduplicated: concurrent callers share one request). */
export function load<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const running = inflight.get(key) as Promise<T> | undefined;
  if (running) return running;
  const prev = read<T>(key);
  write(key, { ...prev, status: prev.data === null ? "loading" : prev.status });
  const p = fetcher()
    .then((data) => {
      write(key, { data, status: "ready", savedAt: Date.now() });
      return data;
    })
    .catch((err) => {
      write(key, { ...read<T>(key), status: "error" });
      throw err;
    })
    .finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

/** Use cached data for `key`, refreshing it from the server when the component mounts. */
export function useResource<T>(key: string | null, fetcher: () => Promise<T>) {
  const subscribe = useCallback((l: () => void) => {
    listeners.add(l);
    return () => listeners.delete(l);
  }, []);
  const entry = useSyncExternalStore(subscribe, () => (key ? read<T>(key) : EMPTY)) as Entry<T>;

  const reload = useCallback(() => {
    if (key) load(key, fetcher).catch(() => {});
    // fetcher is defined inline by callers; the key identifies it.
  }, [key]);

  useEffect(reload, [reload]);
  return { data: entry.data, status: entry.status, reload };
}

const EMPTY: Entry<never> = { data: null, status: "idle", savedAt: 0 };

/** Forget everything (sign-out, account deletion). */
export function clearCache() {
  entries.clear();
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k?.startsWith(PREFIX)) localStorage.removeItem(k);
    }
  } catch {
    /* ignore */
  }
  emit();
}

/** Cache keys, scoped per user so two accounts in one browser never mix data. */
export const keys = {
  dashboard: (userId: string) => `${userId}:dashboard`,
  applications: (userId: string) => `${userId}:applications`,
  application: (userId: string, id: string) => `${userId}:application:${id}`,
};

/** Read cached data without subscribing or fetching. */
export function peek<T>(key: string): T | null {
  return read<T>(key).data;
}
