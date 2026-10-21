import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { api } from "../lib/api";
import { mockApplications, mockStats } from "../data/mock";
import type { Application, ApplicationStats, ApplicationStatus } from "../types";
import { PlusIcon, SearchIcon } from "../components/Icons";
import { Card, ScoreBar, SrOnly, StatusPill, btnPrimary } from "../components/ui";

type Filter = "all" | ApplicationStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "offer", label: "Offer" },
];

export default function Dashboard() {
  const [items, setItems] = useState<Application[]>(mockApplications);
  const [stats, setStats] = useState<ApplicationStats>(mockStats);
  const [usingMock, setUsingMock] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

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
    return items.filter(
      (a) =>
        (filter === "all" || a.status === filter) &&
        (!q || a.company.toLowerCase().includes(q) || a.role.toLowerCase().includes(q)),
    );
  }, [items, filter, query]);

  const tiles = [
    { label: "Applied", value: stats.applied, warn: false },
    { label: "Interviewing", value: stats.interviewing, warn: false },
    { label: "Offers", value: stats.offers, warn: false },
    { label: "Follow-ups due", value: stats.followUpsDue, warn: true },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 text-[28px] font-bold tracking-tight">Applications</h1>
          <p className="mt-1.5 mb-0 text-[15px] text-slate-600">
            Statuses update automatically from your inbox.
            {usingMock && (
              <span className="ml-2 text-slate-500">(showing sample data)</span>
            )}
          </p>
        </div>
        <Link to="/tailor" className={`${btnPrimary} text-[15px]`}>
          <PlusIcon size={16} />
          New tailored resume
        </Link>
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4">
        {tiles.map((t) => (
          <Card key={t.label} className="p-5">
            <div className="text-[13px] text-slate-500">{t.label}</div>
            <div className={`mt-1.5 text-[32px] font-bold ${t.warn ? "text-amber-700" : ""}`}>
              {t.value}
            </div>
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
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs tracking-wide text-slate-500 uppercase">
                <th className="px-5 py-3 font-semibold">Company</th>
                <th className="px-5 py-3 font-semibold">Role</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">ATS match</th>
                <th className="px-5 py-3 font-semibold">Last update</th>
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
                  <td className="px-5 py-3.5 text-slate-600">{a.lastUpdate}</td>
                  <td className="px-5 py-3.5 text-right">
                    <Link
                      to={`/tailor?application=${a.id}`}
                      className="font-semibold text-blue-700 hover:text-blue-800"
                    >
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
