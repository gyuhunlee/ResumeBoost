import { Link } from "react-router";
import { useGmailSync } from "../lib/useGmailSync";
import { formatDateTime } from "../lib/dates";
import { MailIcon } from "./Icons";
import { btnSecondary } from "./ui";

/** "Last synced Oct 27, 2026, 7:46 PM · Sync now", or a prompt to connect Gmail. */
export default function GmailSyncBar() {
  const { status, error, syncing, notice, syncNow } = useGmailSync();
  if (!status) return null; // backend offline

  if (!status.connected) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
        <p className="m-0 flex items-center gap-2 text-sm text-blue-900">
          <MailIcon size={16} />
          Connect Gmail to find your applications and keep their status up to date.
        </p>
        <Link to="/settings#gmail" className={`${btnSecondary} min-h-9 text-sm`}>Connect Gmail</Link>
      </div>
    );
  }

  const failed = status.syncStatus === "error";
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-[13px] text-slate-600">
      <span aria-live="polite" className="flex items-center gap-2">
        <MailIcon size={15} className="text-slate-500" />
        {syncing
          ? "Checking your inbox…"
          : status.lastSyncedAt
            ? <>Last synced <time dateTime={status.lastSyncedAt}>{formatDateTime(status.lastSyncedAt)}</time></>
            : "Not synced yet"}
        {failed && !syncing && (
          <span className="text-red-700">
            · Last sync failed. {status.lastError?.startsWith("Reconnect")
              ? <Link to="/settings#gmail" className="font-semibold text-red-700">Reconnect Gmail</Link>
              : "Try again."}
          </span>
        )}
        {notice && !syncing && <span className="font-medium text-green-700">· {notice}</span>}
        {error && <span className="text-red-700">· {error}</span>}
      </span>
      <button
        type="button"
        onClick={syncNow}
        disabled={syncing}
        className={`${btnSecondary} min-h-9 cursor-pointer px-3.5 text-[13px] disabled:cursor-default disabled:opacity-60`}
      >
        {syncing ? "Syncing…" : "Sync now"}
      </button>
    </div>
  );
}
