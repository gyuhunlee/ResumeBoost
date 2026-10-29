import type { ReactNode } from "react";
import type { ApplicationStatus } from "../types";

// Reusable class strings so buttons and links look identical everywhere.
export const btnPrimary =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-5 font-semibold text-white no-underline transition-colors hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700 disabled:opacity-60";

export const btnSecondary =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-5 font-semibold text-slate-900 no-underline transition-colors hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white ${className}`}>
      {children}
    </div>
  );
}

export function Chip({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "match" | "missing";
}) {
  const styles =
    tone === "match"
      ? "bg-green-50 text-green-700"
      : "bg-orange-50 text-amber-700";
  return (
    <span className={`rounded-md px-2.5 py-1 text-[13px] ${styles}`}>
      {children}
    </span>
  );
}

const STATUS: Record<ApplicationStatus, { label: string; cls: string }> = {
  applied: { label: "Applied", cls: "bg-slate-100 text-slate-700" },
  interviewing: { label: "Interviewing", cls: "bg-blue-50 text-blue-700" },
  offer: { label: "Offer", cls: "bg-green-50 text-green-700" },
  follow_up: { label: "Follow up", cls: "bg-yellow-50 text-yellow-800" },
  rejected: { label: "Rejected", cls: "bg-red-50 text-red-700" },
};

export function StatusPill({ status }: { status: ApplicationStatus }) {
  const s = STATUS[status];
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${s.cls}`}>
      {s.label}
    </span>
  );
}

export const statusLabel = (s: ApplicationStatus) => STATUS[s].label;

/** Pipeline order, used for sorting and for the dashboard ring. */
export const STATUS_ORDER: ApplicationStatus[] = ["applied", "interviewing", "offer", "follow_up", "rejected"];

/** Solid colors for charts and calendar dots (Tailwind slate-400, blue-600, green-600, yellow-500, red-600). */
export const STATUS_COLOR: Record<ApplicationStatus, string> = {
  applied: "#94A3B8",
  interviewing: "#2563EB",
  offer: "#16A34A",
  follow_up: "#EAB308",
  rejected: "#DC2626",
};

/** Text-safe shades of the same colors (pass 4.5:1 on white). */
export const STATUS_TEXT: Record<ApplicationStatus, string> = {
  applied: "#475569",
  interviewing: "#1D4ED8",
  offer: "#15803D",
  follow_up: "#A16207",
  rejected: "#B91C1C",
};

/** Pale tints, for icon backgrounds and dimmed chart slices. */
export const STATUS_TINT: Record<ApplicationStatus, string> = {
  applied: "#E2E8F0",
  interviewing: "#DBEAFE",
  offer: "#DCFCE7",
  follow_up: "#FEF9C3",
  rejected: "#FEE2E2",
};

export function ScoreBar({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div
      className={`h-1.5 overflow-hidden rounded-full bg-slate-200 ${className}`}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="ATS match"
    >
      <div className="h-full rounded-full bg-blue-700" style={{ width: `${value}%` }} />
    </div>
  );
}

export function ScoreRing({ value, size = 120 }: { value: number; size?: number }) {
  const r = 50;
  const circumference = 2 * Math.PI * r;
  const filled = (value / 100) * circumference;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role="img"
      aria-label={`ATS match score ${value} out of 100`}
    >
      <circle cx="60" cy="60" r={r} fill="none" stroke="#E2E8F0" strokeWidth="10" />
      <circle
        cx="60"
        cy="60"
        r={r}
        fill="none"
        stroke="#1D4ED8"
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${filled} ${circumference}`}
        transform="rotate(-90 60 60)"
      />
      <text
        x="60"
        y="66"
        textAnchor="middle"
        fontSize="30"
        fontWeight="700"
        fill="#0F172A"
        fontFamily="Inter, sans-serif"
      >
        {value}
      </text>
    </svg>
  );
}

// Visually hidden text for screen readers.
export function SrOnly({ children }: { children: ReactNode }) {
  return <span className="sr-only">{children}</span>;
}

/** Splits `items` into pages. Clamps the page when the list shrinks (e.g. after a dismiss). */
export function paginate<T>(items: T[], page: number, size: number) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(page, 1), pages);
  return { pageItems: items.slice((current - 1) * size, current * size), page: current, pages };
}

/** "‹  1–5 of 12  ›" control. Renders nothing when everything fits on one page. */
export function Pager({
  page,
  pages,
  total,
  size,
  onPage,
  label,
}: {
  page: number;
  pages: number;
  total: number;
  size: number;
  onPage: (p: number) => void;
  label: string;
}) {
  if (pages <= 1) return null;
  const from = (page - 1) * size + 1;
  const to = Math.min(page * size, total);
  const btn =
    "flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:cursor-default disabled:opacity-35";
  return (
    <nav aria-label={label} className="flex items-center justify-between gap-3 text-[13px] text-slate-600">
      <span aria-live="polite">
        {from}–{to} of {total}
      </span>
      <div className="flex gap-1">
        <button type="button" className={btn} onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Previous page">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <button type="button" className={btn} onClick={() => onPage(page + 1)} disabled={page >= pages} aria-label="Next page">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M9 18l6-6-6-6" /></svg>
        </button>
      </div>
    </nav>
  );
}
