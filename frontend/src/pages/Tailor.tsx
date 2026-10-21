import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../lib/api";
import { mockTailorResult, sampleJobDescription } from "../data/mock";
import type { Rewrite, TailorResult } from "../types";
import { CheckIcon, ChevronLeftIcon, SearchIcon } from "../components/Icons";
import { Card, Chip, ScoreRing, btnPrimary, btnSecondary } from "../components/ui";

const inputCls =
  "min-h-10 rounded-lg border border-slate-300 px-3 text-sm text-slate-900 outline-none focus:border-blue-700";

export default function Tailor() {
  const navigate = useNavigate();
  const [company, setCompany] = useState("Northwind");
  const [role, setRole] = useState("Software Engineer");
  const [jobDescription, setJobDescription] = useState(sampleJobDescription);
  const [result, setResult] = useState<TailorResult>(mockTailorResult);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runTailoring(e?: FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResult(await api.tailor({ company, role, jobDescription }));
    } catch {
      setError("Couldn't reach the API, so sample results are shown.");
      setResult(mockTailorResult);
    } finally {
      setLoading(false);
    }
  }

  // Run once on load so the results panel reflects the backend when it's up.
  useEffect(() => {
    void runTailoring();
  }, []);

  const gain = result.score - result.originalScore;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-4 px-6 py-3.5">
          <div className="flex flex-wrap items-center gap-5">
            <Link
              to="/dashboard"
              className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-slate-600 no-underline hover:text-slate-900"
            >
              <ChevronLeftIcon size={16} />
              Applications
            </Link>
            <h1 className="m-0 text-lg font-semibold">Tailor resume</h1>
          </div>
          <Stepper current={3} />
        </div>
      </header>

      <div className="mx-auto flex max-w-[1280px] flex-wrap items-start gap-6 px-6 pt-7 pb-12">
        {/* Left: job details + company brief */}
        <section aria-label="Job details" className="flex min-w-0 flex-[1_1_380px] flex-col gap-4">
          <Card className="p-5">
            <form onSubmit={runTailoring} className="flex flex-col gap-3.5">
              <h2 className="m-0 text-base font-semibold">Job description</h2>
              <div className="flex flex-wrap gap-3">
                <label className="flex flex-[1_1_140px] flex-col gap-1.5 text-[13px] font-medium text-slate-700">
                  Company
                  <input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} />
                </label>
                <label className="flex flex-[1_1_140px] flex-col gap-1.5 text-[13px] font-medium text-slate-700">
                  Role
                  <input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} />
                </label>
              </div>
              <label className="flex flex-col gap-1.5 text-[13px] font-medium text-slate-700">
                Paste the posting
                <textarea
                  rows={12}
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  className="resize-y rounded-lg border border-slate-300 p-3 text-sm leading-relaxed text-slate-700 outline-none focus:border-blue-700"
                />
              </label>
              <button type="submit" disabled={loading} className={`${btnSecondary} cursor-pointer text-sm`}>
                {loading ? "Tailoring…" : "Re-run tailoring"}
              </button>
              {error && <p className="m-0 text-[13px] text-amber-700">{error}</p>}
            </form>
          </Card>

          <Card className="flex flex-col gap-3 p-5">
            <div className="flex items-center gap-2">
              <SearchIcon size={18} className="text-blue-700" />
              <h2 className="m-0 text-base font-semibold">Company brief</h2>
            </div>
            <p className="m-0 text-sm leading-relaxed text-slate-600">{result.companyBrief.summary}</p>
            <ul className="m-0 pl-[18px] text-sm leading-7 text-slate-700">
              {result.companyBrief.highlights.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </Card>
        </section>

        {/* Right: results */}
        <section aria-label="Results" aria-busy={loading} className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
          <Card className="flex flex-wrap items-center gap-8 p-6">
            <ScoreRing value={result.score} />
            <div className="flex flex-[1_1_240px] flex-col gap-2">
              <div className="text-[13px] text-slate-500">ATS match score</div>
              <div className="text-[22px] font-bold">
                {result.score >= 85 ? "Strong match" : result.score >= 70 ? "Good match" : "Needs work"}{" "}
                {gain > 0 && (
                  <span className="text-[15px] font-medium text-green-700">+{gain} from original</span>
                )}
              </div>
              <p className="m-0 text-sm leading-relaxed text-slate-600">
                {result.matchedKeywords.length} of{" "}
                {result.matchedKeywords.length + result.missingKeywords.length} keywords now appear. Add the
                missing ones only if they reflect real experience.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              {/* Placeholder: replace with a call to a PDF export endpoint. */}
              <button type="button" onClick={() => window.print()} className={`${btnPrimary} cursor-pointer text-sm`}>
                Download PDF
              </button>
              <button type="button" onClick={() => navigate("/dashboard")} className={`${btnSecondary} cursor-pointer text-sm`}>
                Save to applications
              </button>
            </div>
          </Card>

          <Card className="flex flex-col gap-3.5 p-5">
            <h2 className="m-0 text-base font-semibold">Keywords</h2>
            <KeywordGroup label="Matched">
              {result.matchedKeywords.map((k) => (
                <Chip key={k} tone="match">{k}</Chip>
              ))}
            </KeywordGroup>
            {result.missingKeywords.length > 0 && (
              <KeywordGroup label="Missing">
                {result.missingKeywords.map((k) => (
                  <Chip key={k} tone="missing">{k}</Chip>
                ))}
              </KeywordGroup>
            )}
          </Card>

          <Rewrites key={result.rewrites.map((r) => r.id).join()} rewrites={result.rewrites} />
        </section>
      </div>
    </div>
  );
}

function Stepper({ current }: { current: number }) {
  const steps = ["Resume", "Job description", "Review", "Export"];
  return (
    <ol aria-label="Progress" className="m-0 flex list-none flex-wrap gap-2 p-0 text-[13px]">
      {steps.map((label, i) => {
        const n = i + 1;
        const done = n < current;
        const active = n === current;
        const cls = done
          ? "bg-green-50 font-semibold text-green-700"
          : active
            ? "bg-blue-700 font-semibold text-white"
            : "bg-slate-100 font-medium text-slate-600";
        return (
          <li
            key={label}
            aria-current={active ? "step" : undefined}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 ${cls}`}
          >
            {done ? <CheckIcon size={14} /> : `${n} ·`} {label}
          </li>
        );
      })}
    </ol>
  );
}

function KeywordGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{label}</div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function Rewrites({ rewrites }: { rewrites: Rewrite[] }) {
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});

  const acceptedCount = rewrites.filter((r) => accepted[r.id]).length;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <h2 className="m-0 text-base font-semibold">Suggested rewrites</h2>
        <span className="text-[13px] text-slate-500" aria-live="polite">
          {acceptedCount} of {rewrites.length} accepted
        </span>
      </div>

      {rewrites.map((r) => {
        const text = edits[r.id] ?? r.after;
        const isAccepted = !!accepted[r.id];
        const isEditing = editing === r.id;
        return (
          <div key={r.id} className="flex flex-wrap items-start gap-5 border-t border-slate-100 px-5 py-4.5 first-of-type:border-t-0">
            <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-2">
              <div className="text-xs font-semibold text-slate-500">{r.section}</div>
              <div className="text-sm leading-normal text-slate-400 line-through">{r.before}</div>
              {isEditing ? (
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  Edit rewrite
                  <textarea
                    autoFocus
                    rows={3}
                    value={text}
                    onChange={(e) => setEdits({ ...edits, [r.id]: e.target.value })}
                    className="rounded-lg border border-slate-300 p-2.5 text-sm text-slate-900 outline-none focus:border-blue-700"
                  />
                </label>
              ) : (
                <div className="text-sm leading-normal">{text}</div>
              )}
            </div>

            <div className="flex gap-2">
              {isEditing ? (
                <button type="button" onClick={() => setEditing(null)} className={`${btnPrimary} min-h-10 cursor-pointer px-3.5 text-[13px]`}>
                  Done
                </button>
              ) : isAccepted ? (
                <button
                  type="button"
                  aria-pressed="true"
                  onClick={() => setAccepted({ ...accepted, [r.id]: false })}
                  className="inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-lg border border-green-700 bg-green-50 px-3.5 text-[13px] font-semibold text-green-700"
                >
                  <CheckIcon size={14} />
                  Accepted
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => setAccepted({ ...accepted, [r.id]: true })}
                    className={`${btnPrimary} min-h-10 cursor-pointer px-3.5 text-[13px]`}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(r.id)}
                    className={`${btnSecondary} min-h-10 cursor-pointer px-3.5 text-[13px]`}
                  >
                    Edit
                  </button>
                </>
              )}
            </div>
          </div>
        );
      })}
    </Card>
  );
}
