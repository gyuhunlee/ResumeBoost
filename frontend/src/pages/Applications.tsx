import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { api } from "../lib/api";
import { formatRelativeDate } from "../lib/dates";
import { mockApplications, mockStats } from "../data/mock";
import type { Application, ApplicationStats, ApplicationStatus } from "../types";
import { SearchIcon } from "../components/Icons";
import { Card, STATUS_ORDER, ScoreBar, SrOnly, StatusPill } from "../components/ui";

type Filter = "all" | ApplicationStatus;
type SortKey = "company" | "role" | "status" | "atsScore" | "lastUpdateAt";
type SortDir = "asc" | "desc";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "offer", label: "Offer" },
  { value: "follow_up", label: "Follow up" },
  { value: "rejected", label: "Rejected" },
];

const COLUMNS: { key: SortKey; label: string; firstDir: SortDir }[] = [
  { key: "company", label: "Company", firstDir: "asc" },
  { key: "role", label: "Role", firstDir: "asc" },
  { key: "status", label: "Status", firstDir: "asc" },
  { key: "atsScore", label: "ATS match", firstDir: "desc" },
  { key: "lastUpdateAt", label: "Last update", firstDir: "desc" },
];

function compare(a: Application, b: Application, key: SortKey): number {
  switch (key) {
    case "company":
    case "role":
      return a[key].localeCompare(b[key], undefined, { sensitivity: "base" });
    case "status":
      return STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status);
    case "atsScore":
      return a.atsScore - b.atsScore;
    case "lastUpdateAt":
      return a.lastUpdateAt.localeCompare(b.lastUpdateAt); // ISO dates sort as strings
  }
}

function SortArrows({ dir }: { dir: SortDir | null }) {
  return (
    <svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true" className="shrink-0">
      <path d="M5 1L9 5.5H1z" fill={dir === "asc" ? "#1D4ED8" : "#CBD5E1"} />
      <path d="M5 13L1 8.5h8z" fill={dir === "desc" ? "#1D4ED8" : "#CBD5E1"} />
    </svg>
  );
}

export default function Applications() {
  const [items, setItems] = useState<Application[]>(mockApplications);
  const [stats, setStats] = useState<ApplicationStats>(mockStats);
  const [usingMock, setUsingMock] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: "lastUpdateAt", dir: "desc" });

  useEffect(() => {
    // Load from the FastAPI backend; keep the sample data if it isn't running.
    api
      .listApplications()
      .then((data) => {
        setItems(data.items);
        setStats(data.stats);
        setUsingMock(false);
      })
      .catch(() => setUsingMock(true));
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const sign = sort.dir === "asc" ? 1 : -1;
    return items
      .filter(
        (a) =>
          (filter === "all" || a.status === filter) &&
          (!q || a.company.toLowerCase().includes(q) || a.role.toLowerCase().includes(q)),
      )
      .sort((a, b) => sign * compare(a, b, sort.key));
  }, [items, filter, query, sort]);

  const toggleSort = (key: SortKey, firstDir: SortDir) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: firstDir }));

  const tiles = [
    { label: "Applied", value: stats.applied, warn: false },
    { label: "Interviewing", value: stats.interviewing, warn: false },
    { label: "Offers", value: stats.offers, warn: false },
    { label: "Follow-ups due", value: stats.followUpsDue, warn: true },
  ];

  return (
    <div className="mx-auto flex max-w-[1240px] flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 text-[28px] font-bold tracking-tight">Applications</h1>
          <p className="mt-1.5 mb-0 text-[15px] text-slate-600">
            Statuses update automatically from your inbox.
            {usingMock && <span className="ml-2 text-slate-500">(showing sample data)</span>}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4">
        {tiles.map((t) => (
          <Card key={t.label} className="p-5">
            <div className="text-[13px] text-slate-500">{t.label}</div>
            <div className={`mt-1.5 text-[32px] font-bold ${t.warn ? "text-amber-700" : ""}`}>{t.value}</div>
          </Card>
        ))}
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
            {FILTERS.map((f) => {
              const active = filter === f.value;
              return (
                <button
                  key={f.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setFilter(f.value)}
                  className={`min-h-9 cursor-pointer rounded-full border px-3.5 text-[13px] ${
                    active
                      ? "border-slate-900 bg-slate-900 font-semibold text-white"
                      : "border-slate-300 bg-white font-medium text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {f.label}
                </button>
              );
            })}
          </div>
          <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 px-3 focus-within:border-blue-700">
            <SearchIcon size={16} className="text-slate-500" />
            <SrOnly>Search applications</SrOnly>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search company or role"
              className="w-52 bg-transparent text-sm text-slate-900 outline-none"
            />
          </label>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead>
              <tr className="text-left">
                {COLUMNS.map((c) => {
                  const active = sort.key === c.key;
                  return (
                    <th
                      key={c.key}
                      scope="col"
                      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                      className="px-3 py-1.5 first:pl-3.5"
                    >
                      <button
                        type="button"
                        onClick={() => toggleSort(c.key, c.firstDir)}
                        className={`inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-md px-2 text-xs font-semibold tracking-wide uppercase ${
                          active ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                        }`}
                      >
                        {c.label}
                        <SortArrows dir={active ? sort.dir : null} />
                      </button>
                    </th>
                  );
                })}
                <th className="px-5 py-3">
                  <SrOnly>Actions</SrOnly>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="px-5 py-3.5 font-semibold">{a.company}</td>
                  <td className="px-5 py-3.5 text-slate-700">{a.role}</td>
                  <td className="px-5 py-3.5">
                    <StatusPill status={a.status} />
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <ScoreBar value={a.atsScore} className="w-20" />
                      <span className="font-semibold">{a.atsScore}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">
                    <time dateTime={a.lastUpdateAt}>{formatRelativeDate(a.lastUpdateAt)}</time>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <Link to={`/tailor?application=${a.id}`} className="font-semibold text-blue-700 hover:text-blue-800">
                      Open<SrOnly> {a.company}</SrOnly>
                    </Link>
                  </td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                    No applications match.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
