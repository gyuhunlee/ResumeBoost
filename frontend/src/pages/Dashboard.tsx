import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { api } from "../lib/api";
import { toISODate } from "../lib/dates";
import { mockDashboard } from "../data/mock";
import type { DashboardData } from "../types";
import { useAuth } from "../auth/AuthProvider";
import { PlusIcon } from "../components/Icons";
import { btnPrimary } from "../components/ui";
import StatusRing from "../components/dashboard/StatusRing";
import CalendarCard from "../components/dashboard/CalendarCard";
import RemindersPanel from "../components/dashboard/RemindersPanel";
import GmailSyncBar from "../components/GmailSyncBar";
import { keys, useResource } from "../lib/store";

// Dismissed reminders are remembered per user in this browser.
// TODO: store them on the server once reminders live in the database.
const dismissedKey = (userId: string) => `rb:dismissed-reminders:${userId}`;

function loadDismissed(userId: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(dismissedKey(userId)) ?? "[]"));
  } catch {
    return new Set();
  }
}

function saveDismissed(userId: string, ids: Set<string>) {
  try {
    localStorage.setItem(dismissedKey(userId), JSON.stringify([...ids]));
  } catch {
    // Storage can be unavailable (private mode); dismissals then last for this visit only.
  }
}

export default function Dashboard() {
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  // Cached data shows instantly; it refreshes in the background.
  const res = useResource<DashboardData>(keys.dashboard(userId), api.getDashboard);
  // Sample data only when the server can't be reached and nothing is cached.
  const usingMock = res.data === null && res.status === "error";
  const data = res.data ?? (usingMock ? mockDashboard : null);
  const [dismissed, setDismissed] = useState<Set<string>>(() => loadDismissed(userId));


  useEffect(() => setDismissed(loadDismissed(userId)), [userId]);

  // The calendar only covers time since the user joined: an email from the day
  // before they signed up (say, a rejection) never shows on it.
  const signedUpAt = session?.user.created_at ? new Date(session.user.created_at) : null;
  const signupISO = signedUpAt ? toISODate(signedUpAt) : null;
  const events = useMemo(
    () => (!data ? [] : signupISO ? data.events.filter((e) => e.date >= signupISO) : data.events),
    [data, signupISO],
  );

  const todayISO = toISODate(new Date());
  const reminders = useMemo(
    () =>
      (data?.reminders ?? [])
        .filter((r) => r.date >= todayISO && !dismissed.has(r.id))
        .sort((a, b) => (a.date + (a.time ?? "")).localeCompare(b.date + (b.time ?? ""))),
    [data, dismissed, todayISO],
  );

  const updateDismissed = (ids: Iterable<string>) => {
    const next = new Set(dismissed);
    for (const id of ids) next.add(id);
    setDismissed(next);
    saveDismissed(userId, next);
  };

  const todayLabel = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  return (
    <div className="mx-auto flex max-w-[1240px] flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 text-[28px] font-bold tracking-tight">Dashboard</h1>
          <p className="mt-1.5 mb-0 text-[15px] text-slate-600">
            {todayLabel}
            {usingMock && <span className="ml-2 text-slate-500">(showing sample data)</span>}
          </p>
        </div>
        <Link to="/tailor" className={`${btnPrimary} text-[15px]`}>
          <PlusIcon size={16} />
          New tailored resume
        </Link>
      </div>

      <GmailSyncBar />

      {!data ? (
        <DashboardSkeleton />
      ) : (
      <div className="flex flex-wrap items-stretch gap-6">
        <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-6">
          <StatusRing counts={data.counts} />
          <CalendarCard events={events} signedUpAt={signedUpAt} />
        </div>
        <RemindersPanel
          reminders={reminders}
          onDismiss={(id) => updateDismissed([id])}
          onClearAll={() => updateDismissed(reminders.map((r) => r.id))}
        />
      </div>
      )}
    </div>
  );
}

/** Placeholder shapes for the first visit, before any data has been cached. */
function DashboardSkeleton() {
  const block = "animate-pulse rounded-xl border border-slate-200 bg-white";
  return (
    <div className="flex flex-wrap items-stretch gap-6" aria-busy="true" aria-label="Loading dashboard">
      <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-6">
        <div className={`${block} h-56`} />
        <div className={`${block} h-[440px]`} />
      </div>
      <div className={`${block} min-h-80 flex-[1_1_340px]`} />
    </div>
  );
}
