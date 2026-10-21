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
  follow_up: { label: "Follow up", cls: "bg-orange-50 text-amber-700" },
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
