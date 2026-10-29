// Date helpers. Dates travel as "YYYY-MM-DD" strings and are read in the
// user's local time zone, so "today" always means the user's today.

const DAY_MS = 86_400_000;

export function toISODate(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function parseISODate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

/** Whole days from `a` to `b` (positive when b is later). Safe across DST changes. */
export function daysBetween(a: Date, b: Date): number {
  return Math.round((startOfDay(b).getTime() - startOfDay(a).getTime()) / DAY_MS);
}

/** "Today", "Yesterday", "Oct 15", or "Oct 15, 2025" for another year. */
export function formatRelativeDate(iso: string, today = new Date()): string {
  const d = parseISODate(iso);
  const diff = daysBetween(d, today);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  if (d.getFullYear() !== today.getFullYear()) opts.year = "numeric";
  return d.toLocaleDateString("en-US", opts);
}

/** "Today", "Tomorrow", or "Wed, Oct 28" for an upcoming date. */
export function formatUpcomingDay(iso: string, today = new Date()): string {
  const d = parseISODate(iso);
  const diff = daysBetween(today, d);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  const opts: Intl.DateTimeFormatOptions = { weekday: "short", month: "short", day: "numeric" };
  if (d.getFullYear() !== today.getFullYear()) opts.year = "numeric";
  return d.toLocaleDateString("en-US", opts);
}

/** "14:30" → "2:30 PM". */
export function formatTime(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  return new Date(2000, 0, 1, h, m).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

/** "Oct 27, 2026, 7:46 PM" in the user's time zone, from an ISO date-time. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

/** "Today, 7:46 PM", "Yesterday, 9:02 AM", or "Oct 15, 3:10 PM" (year added when it differs). */
export function formatRelativeDateTime(iso: string, today = new Date()): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return `${formatRelativeDate(toISODate(d), today)}, ${time}`;
}
