import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import { keys, load } from "./store";
import type { GmailStatus } from "../types";

/** A sync older than this starts automatically when the app opens. */
const STALE_MS = 15 * 60 * 1000;
const POLL_MS = 2000;
const MAX_POLL_MS = 3 * 60 * 1000;

type GmailSync = {
  /** null while loading, or when the backend is offline. */
  status: GmailStatus | null;
  syncing: boolean;
  error: string | null;
  /** Shown briefly after a sync: "2 applications updated" / "No new updates". */
  notice: string | null;
  syncNow: () => Promise<void>;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
};

const Ctx = createContext<GmailSync | null>(null);

/**
 * One Gmail sync state for the whole app (mounted in AppLayout), so the
 * "Sync now" buttons on Dashboard, Applications and Settings all share it,
 * and a finished sync refreshes every page's data at once.
 */
export function GmailSyncProvider({ userId, children }: { userId: string; children: ReactNode }) {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const busy = useRef(false);
  const noticeTimer = useRef<number | undefined>(undefined);

  const refreshData = useCallback(() => {
    // Reload what the pages show. Ignore errors: the pages keep their cached data.
    load(keys.dashboard(userId), api.getDashboard).catch(() => {});
    load(keys.applications(userId), api.listApplications).catch(() => {});
  }, [userId]);

  const flash = (text: string) => {
    setNotice(text);
    window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(null), 6000);
  };

  /** Wait for a sync started elsewhere (first backfill, another tab, daily job). */
  const waitForSync = useCallback(async () => {
    const started = Date.now();
    while (Date.now() - started < MAX_POLL_MS) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      try {
        const s = await api.gmailStatus();
        setStatus(s);
        if (s.syncStatus !== "running") return;
      } catch {
        /* keep waiting through network hiccups */
      }
    }
  }, []);

  const syncNow = useCallback(async () => {
    if (busy.current) return; // a second click while syncing does nothing
    busy.current = true;
    setSyncing(true);
    setError(null);
    try {
      const s = await api.gmailSync(); // returns when the sync has finished
      setStatus(s);
      if (s.syncStatus === "running") await waitForSync();
      refreshData();
      if (s.syncStatus === "error") return;
      if (s.changed != null) {
        flash(s.changed === 0 ? "No new updates" : `${s.changed} application update${s.changed === 1 ? "" : "s"}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't sync. Try again.");
    } finally {
      busy.current = false;
      setSyncing(false);
    }
  }, [refreshData, waitForSync]);

  // On app open: load the status, and sync if the last sync is stale.
  useEffect(() => {
    let cancelled = false;
    api
      .gmailStatus()
      .then(async (s) => {
        if (cancelled) return;
        setStatus(s);
        if (!s.connected) return;
        if (s.syncStatus === "running") {
          setSyncing(true);
          await waitForSync();
          setSyncing(false);
          refreshData();
          return;
        }
        const age = s.lastSyncedAt ? Date.now() - new Date(s.lastSyncedAt).getTime() : Infinity;
        if (age > STALE_MS) void syncNow();
      })
      .catch(() => !cancelled && setStatus(null));
    return () => {
      cancelled = true;
    };
  }, [refreshData, syncNow, waitForSync]);

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

  return (
    <Ctx.Provider value={{ status, syncing, error, notice, syncNow, connect, disconnect }}>
      {children}
    </Ctx.Provider>
  );
}

export function useGmailSync(): GmailSync {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useGmailSync must be used inside <GmailSyncProvider>");
  return ctx;
}
