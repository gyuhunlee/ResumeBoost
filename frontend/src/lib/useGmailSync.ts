import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { GmailStatus } from "../types";

/** A sync older than this starts automatically when a page loads. */
const STALE_MS = 15 * 60 * 1000;
const POLL_MS = 2500;
const MAX_POLL_MS = 3 * 60 * 1000;

/**
 * Gmail sync state for a page. The server does the work in the background;
 * this hook starts a sync when the data is stale (or on "Sync now"), polls
 * until it finishes, then calls `onSynced` so the page reloads its data.
 */
export function useGmailSync(onSynced?: () => void, { autoSync = true } = {}) {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const onSyncedRef = useRef(onSynced);
  onSyncedRef.current = onSynced;
  const pollTimer = useRef<number | undefined>(undefined);

  const stopPolling = () => window.clearTimeout(pollTimer.current);

  const poll = useCallback((startedAt: number) => {
    stopPolling();
    pollTimer.current = window.setTimeout(async () => {
      try {
        const s = await api.gmailStatus();
        setStatus(s);
        if (s.syncStatus === "running" && Date.now() - startedAt < MAX_POLL_MS) {
          poll(startedAt);
        } else {
          onSyncedRef.current?.();
        }
      } catch {
        // Network hiccup: try again until the time limit.
        if (Date.now() - startedAt < MAX_POLL_MS) poll(startedAt);
      }
    }, POLL_MS);
  }, []);

  const syncNow = useCallback(async () => {
    setError(null);
    try {
      setStatus(await api.gmailSync());
      poll(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start a sync.");
    }
  }, [poll]);

  const refresh = useCallback(async () => {
    try {
      const s = await api.gmailStatus();
      setStatus(s);
      return s;
    } catch {
      setStatus(null); // backend offline: hide the bar, pages show sample data
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    refresh().then((s) => {
      if (cancelled || !s?.connected) return;
      if (s.syncStatus === "running") return poll(Date.now());
      const age = s.lastSyncedAt ? Date.now() - new Date(s.lastSyncedAt).getTime() : Infinity;
      if (autoSync && age > STALE_MS) void syncNow();
    });
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [autoSync, poll, refresh, syncNow]);

  const connect = useCallback(async () => {
    setError(null);
    try {
      const { url } = await api.gmailConnectUrl();
      window.location.assign(url); // Google consent screen, then back to /settings
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the Gmail connection.");
    }
  }, []);

  const disconnect = useCallback(async () => {
    setError(null);
    try {
      await api.gmailDisconnect();
      setStatus({ connected: false });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't disconnect Gmail.");
    }
  }, []);

  return {
    status,
    error,
    syncing: status?.syncStatus === "running",
    syncNow,
    connect,
    disconnect,
    refresh,
  };
}
