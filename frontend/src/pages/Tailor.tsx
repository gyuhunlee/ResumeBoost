import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../lib/api";
import { fileUrl, listResumes, type Resume } from "../lib/resumes";
import { clearCache } from "../lib/store";
import type {
  TailorAction,
  TailorAnswer,
  TailorChange,
  TailorSession,
  TailorScore,
  TailorStatus,
} from "../types";
import { CheckIcon, ChevronLeftIcon, SparkleIcon } from "../components/Icons";
import { Card, Chip, ScoreRing, btnPrimary, btnSecondary } from "../components/ui";

const inputCls =
  "min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-blue-700 disabled:bg-slate-50 disabled:text-slate-500";
const labelCls = "flex flex-col gap-1.5 text-[13px] font-medium text-slate-700";
const POLL_MS = 2000;

type Decision = { action: TailorAction; text?: string };

export default function Tailor() {
  const [params, setParams] = useSearchParams();
  const sessionId = params.get("session");
  const [session, setSession] = useState<TailorSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load (or reload after a refresh) the session named in the URL.
  useEffect(() => {
    if (!sessionId) {
      setSession(null);
      return;
    }
    if (session?.id === sessionId) return;
    api.getTailorSession(sessionId).then(setSession).catch((e: Error) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Poll while the agent is working.
  useEffect(() => {
    if (!session || session.status !== "running") return;
    const id = window.setInterval(() => {
      api.getTailorSession(session.id).then(setSession).catch(() => {}); // keep polling through blips
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [session?.id, session?.status]);

  function started(s: TailorSession) {
    setSession(s);
    setParams({ session: s.id });
  }

  function reset() {
    setSession(null);
    setError(null);
    setParams({});
  }

  const status = session?.status;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-4 px-6 py-3.5">
          <div className="flex flex-wrap items-center gap-5">
            <Link
              to="/applications"
              className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-slate-600 no-underline hover:text-slate-900"
            >
              <ChevronLeftIcon size={16} />
              Applications
            </Link>
            <h1 className="m-0 text-lg font-semibold">Tailor resume</h1>
          </div>
          <Stepper status={status} />
        </div>
      </header>

      <div className="mx-auto flex max-w-[1280px] flex-wrap items-start gap-6 px-6 pt-7 pb-12">
        <section aria-label="Job details" className="flex min-w-0 flex-[1_1_360px] flex-col gap-4">
          {session ? (
            <JobSummary session={session} onNew={reset} />
          ) : (
            <StartForm onStarted={started} />
          )}
          {session && session.steps.length > 0 && <Activity session={session} />}
        </section>

        <section aria-label="Results" aria-busy={status === "running"} className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
          {error && (
            <Card className="p-5">
              <p role="alert" className="m-0 text-sm text-red-700">{error}</p>
            </Card>
          )}
          {!session && !error && <HowItWorks />}
          {status === "running" && <Working session={session!} />}
          {status === "needs_input" && <Questions session={session!} onUpdated={setSession} />}
          {(status === "review" || status === "finalized") && <Review session={session!} onUpdated={setSession} />}
          {status === "error" && (
            <Card className="flex flex-col gap-3 p-6">
              <h2 className="m-0 text-base font-semibold">Tailoring stopped</h2>
              <p role="alert" className="m-0 text-sm text-red-700">{session!.error ?? "Something went wrong."}</p>
              <button type="button" onClick={reset} className={`${btnSecondary} w-fit cursor-pointer text-sm`}>
                Start over
              </button>
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}

// ---- Left column -------------------------------------------------------------------

function StartForm({ onStarted }: { onStarted: (s: TailorSession) => void }) {
  const [resumes, setResumes] = useState<Resume[] | null>(null);
  const [resumeId, setResumeId] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listResumes()
      .then((rs) => {
        setResumes(rs);
        if (rs[0]) setResumeId(rs[0].id);
      })
      .catch(() => setResumes([]));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onStarted(await api.startTailor({ company, role, jobDescription, resumeId: resumeId || null }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start tailoring.");
      setBusy(false);
    }
  }

  const noResume = resumes !== null && resumes.length === 0;
  const tooShort = jobDescription.trim().length < 50;

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="flex flex-col gap-3.5">
        <h2 className="m-0 text-base font-semibold">Job details</h2>

        {noResume ? (
          <p className="m-0 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
            Upload your resume in <Link to="/settings">Settings</Link> first.
          </p>
        ) : (
          <label className={labelCls}>
            Resume
            <select
              className={inputCls}
              value={resumeId}
              onChange={(e) => setResumeId(e.target.value)}
              disabled={resumes === null}
            >
              {resumes === null && <option>Loading…</option>}
              {resumes?.map((r) => (
                <option key={r.id} value={r.id}>{r.title}</option>
              ))}
            </select>
          </label>
        )}

        <div className="flex flex-wrap gap-3">
          <label className={`${labelCls} flex-[1_1_140px]`}>
            Company
            <input className={inputCls} value={company} required maxLength={200} onChange={(e) => setCompany(e.target.value)} />
          </label>
          <label className={`${labelCls} flex-[1_1_140px]`}>
            Role
            <input className={inputCls} value={role} required maxLength={200} onChange={(e) => setRole(e.target.value)} />
          </label>
        </div>
        <label className={labelCls}>
          Paste the job posting
          <textarea
            rows={14}
            value={jobDescription}
            required
            maxLength={20000}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Responsibilities, requirements, nice-to-haves…"
            className="resize-y rounded-lg border border-slate-300 p-3 text-sm leading-relaxed text-slate-700 outline-none focus:border-blue-700"
          />
        </label>
        <button
          type="submit"
          disabled={busy || noResume || tooShort || !company.trim() || !role.trim()}
          className={`${btnPrimary} cursor-pointer text-sm`}
        >
          <SparkleIcon size={16} />
          {busy ? "Starting…" : "Tailor my resume"}
        </button>
        {error && <p role="alert" className="m-0 text-[13px] text-red-700">{error}</p>}
      </form>
    </Card>
  );
}

function JobSummary({ session, onNew }: { session: TailorSession; onNew: () => void }) {
  return (
    <Card className="flex flex-col gap-2 p-5">
      <div className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Tailoring for</div>
      <div className="text-lg font-semibold">{session.role}</div>
      <div className="text-sm text-slate-600">{session.company}</div>
      <button type="button" onClick={onNew} className={`${btnSecondary} mt-2 w-fit cursor-pointer text-sm`}>
        New job
      </button>
    </Card>
  );
}

function Activity({ session }: { session: TailorSession }) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <h2 className="m-0 text-base font-semibold">Agent activity</h2>
      <ol className="m-0 flex list-none flex-col gap-2.5 p-0" aria-live="polite">
        {session.steps.map((s, i) => (
          <li key={`${s.at}-${i}`} className="flex gap-2.5 text-sm leading-snug text-slate-700">
            <span
              aria-hidden
              className={`mt-1.5 size-2 shrink-0 rounded-full ${s.tool === "error" || s.tool === "limit" ? "bg-amber-500" : "bg-blue-600"}`}
            />
            {s.summary}
          </li>
        ))}
        {session.status === "running" && (
          <li className="flex gap-2.5 text-sm text-slate-500">
            <span aria-hidden className="mt-1.5 size-2 shrink-0 animate-pulse rounded-full bg-slate-400" />
            Working…
          </li>
        )}
      </ol>
    </Card>
  );
}

// ---- Right column ------------------------------------------------------------------

function HowItWorks() {
  const items = [
    ["Reads both", "Your resume is split into sections and bullets; the posting into required and preferred keywords."],
    ["Finds gaps", "Checks which keywords are missing, searches your experience bank, and asks you before assuming."],
    ["Edits with guardrails", "Rewrites bullets to surface real experience. Any new number or skill not backed by your facts is blocked."],
    ["You decide", "Accept, edit or reject each change, then download a clean PDF or Word file."],
  ];
  return (
    <Card className="flex flex-col gap-4 p-6">
      <h2 className="m-0 text-base font-semibold">How tailoring works</h2>
      <ol className="m-0 flex list-none flex-col gap-3.5 p-0">
        {items.map(([title, body], i) => (
          <li key={title} className="flex gap-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-50 text-[13px] font-semibold text-blue-700">
              {i + 1}
            </span>
            <div>
              <div className="text-sm font-semibold">{title}</div>
              <div className="text-sm leading-relaxed text-slate-600">{body}</div>
            </div>
          </li>
        ))}
      </ol>
      <p className="m-0 text-[13px] text-slate-500">
        Tip: add projects and skills that aren't on your resume to the experience bank in <Link to="/settings">Settings</Link>.
      </p>
    </Card>
  );
}

function Working({ session }: { session: TailorSession }) {
  return (
    <Card className="flex flex-col items-start gap-3 p-6">
      <div className="flex items-center gap-3">
        <span aria-hidden className="size-5 animate-spin rounded-full border-2 border-blue-700 border-t-transparent" />
        <h2 className="m-0 text-base font-semibold">Tailoring your resume…</h2>
      </div>
      <p className="m-0 text-sm leading-relaxed text-slate-600">
        This usually takes 20–60 seconds. You can leave this page; the link keeps your progress.
      </p>
      {session.baseline && (
        <p className="m-0 text-sm text-slate-600">
          Current match score: <span className="font-semibold text-slate-900">{session.baseline.score}</span>
        </p>
      )}
    </Card>
  );
}

function Questions({ session, onUpdated }: { session: TailorSession; onUpdated: (s: TailorSession) => void }) {
  const open = session.questions.filter((q) => !q.answered);
  const [answers, setAnswers] = useState<Record<string, TailorAnswer>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (id: string, patch: Partial<TailorAnswer>) =>
    setAnswers((a) => ({ ...a, [id]: { ...(a[id] ?? { questionId: id, confirmed: null, detail: "" }), ...patch } }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const list = open.map((q) => answers[q.id] ?? { questionId: q.id, confirmed: null, detail: "" });
      onUpdated(await api.answerTailor(session.id, list));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send your answers.");
      setBusy(false);
    }
  }

  return (
    <Card className="p-6">
      <form onSubmit={submit} className="flex flex-col gap-5">
        <div>
          <h2 className="m-0 text-base font-semibold">A few quick questions</h2>
          <p className="mt-1 mb-0 text-sm text-slate-600">
            The agent only adds experience you confirm. Answer “No” or skip if it doesn't apply.
          </p>
        </div>
        {open.map((q) => {
          const a = answers[q.id];
          return (
            <fieldset key={q.id} className="m-0 flex flex-col gap-2.5 rounded-xl border border-slate-200 p-4">
              <legend className="sr-only">{q.question}</legend>
              <div className="text-sm font-medium text-slate-900">{q.question}</div>
              {q.keyword && <div><Chip tone="missing">{q.keyword}</Chip></div>}
              <div className="flex gap-2" role="radiogroup" aria-label={q.question}>
                {([["Yes", true], ["No", false]] as const).map(([label, value]) => (
                  <button
                    key={label}
                    type="button"
                    role="radio"
                    aria-checked={a?.confirmed === value}
                    onClick={() => set(q.id, { confirmed: a?.confirmed === value ? null : value })}
                    className={`min-h-10 cursor-pointer rounded-lg border px-4 text-sm font-semibold ${
                      a?.confirmed === value
                        ? "border-blue-700 bg-blue-50 text-blue-700"
                        : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {a?.confirmed === true && (
                <label className={labelCls}>
                  Where did you use it? (helps the agent word it accurately)
                  <input
                    className={inputCls}
                    maxLength={500}
                    value={a.detail}
                    onChange={(e) => set(q.id, { detail: e.target.value })}
                    placeholder="e.g. Used Docker to containerize my capstone API"
                  />
                </label>
              )}
            </fieldset>
          );
        })}
        <div className="flex items-center gap-3">
          <button type="submit" disabled={busy} className={`${btnPrimary} cursor-pointer text-sm`}>
            {busy ? "Sending…" : "Continue"}
          </button>
          {error && <p role="alert" className="m-0 text-[13px] text-red-700">{error}</p>}
        </div>
      </form>
    </Card>
  );
}

function Review({ session, onUpdated }: { session: TailorSession; onUpdated: (s: TailorSession) => void }) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initFor = useRef<string | null>(null);

  // Default every change to "accept" once per session.
  useEffect(() => {
    if (initFor.current === session.id) return;
    initFor.current = session.id;
    setDecisions(Object.fromEntries(session.changes.map((c) => [c.id, { action: "accept" as const }])));
  }, [session.id, session.changes]);

  const accepted = session.changes.filter((c) => decisions[c.id]?.action !== "reject").length;
  const finalized = session.status === "finalized";

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const list = session.changes.map((c) => ({
        changeId: c.id,
        action: decisions[c.id]?.action ?? "accept",
        text: decisions[c.id]?.action === "edit" ? decisions[c.id]?.text ?? "" : null,
      }));
      onUpdated(await api.finalizeTailor(session.id, list));
      clearCache(); // Applications / Dashboard should refetch the new row
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the resume.");
    } finally {
      setBusy(false);
    }
  }

  const setAll = (action: TailorAction) =>
    setDecisions(Object.fromEntries(session.changes.map((c) => [c.id, { action }])));

  return (
    <>
      <ScoreCard session={session} />

      {session.summary && (
        <Card className="flex gap-3 p-5">
          <SparkleIcon size={18} className="mt-0.5 shrink-0 text-blue-700" />
          <p className="m-0 text-sm leading-relaxed text-slate-700">{session.summary}</p>
        </Card>
      )}

      {(session.projected ?? session.baseline) && <Keywords score={(session.projected ?? session.baseline)!} />}

      {session.changes.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="m-0 text-base font-semibold">Proposed changes</h2>
              <span className="text-[13px] text-slate-500" aria-live="polite">
                {accepted} of {session.changes.length} kept
              </span>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setAll("accept")} className={`${btnSecondary} min-h-9 cursor-pointer px-3 text-[13px]`}>
                Accept all
              </button>
              <button type="button" onClick={() => setAll("reject")} className={`${btnSecondary} min-h-9 cursor-pointer px-3 text-[13px]`}>
                Reject all
              </button>
            </div>
          </div>
          {session.changes.map((c) => (
            <ChangeRow
              key={c.id}
              change={c}
              decision={decisions[c.id] ?? { action: "accept" }}
              onChange={(d) => setDecisions((all) => ({ ...all, [c.id]: d }))}
            />
          ))}
        </Card>
      )}

      {session.formatIssues.length > 0 && (
        <Card className="flex flex-col gap-2.5 p-5">
          <h2 className="m-0 text-base font-semibold">Format check</h2>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {session.formatIssues.map((i, n) => (
              <li key={n} className="flex gap-2.5 text-sm leading-snug text-slate-700">
                <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-full ${i.severity === "warning" ? "bg-amber-500" : "bg-slate-400"}`} />
                {i.message}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="text-sm text-slate-600">
          {finalized
            ? "Saved to Applications. Change your decisions and re-create any time."
            : "Creates a PDF and Word file with the changes you kept, and saves the job to Applications."}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={create} disabled={busy} className={`${btnPrimary} cursor-pointer text-sm`}>
            {busy ? "Creating…" : finalized ? "Re-create resume" : "Create tailored resume"}
          </button>
        </div>
        {error && <p role="alert" className="m-0 w-full text-[13px] text-red-700">{error}</p>}
      </Card>
    </>
  );
}

function ScoreCard({ session }: { session: TailorSession }) {
  const finalized = session.status === "finalized";
  const before = session.baseline?.score ?? 0;
  const after = finalized ? session.finalScore ?? before : session.projected?.score ?? before;
  const gain = after - before;

  async function open(path?: string | null) {
    if (path) window.open(await fileUrl(path), "_blank", "noopener");
  }

  return (
    <Card className="flex flex-wrap items-center gap-8 p-6">
      <ScoreRing value={after} />
      <div className="flex flex-[1_1_240px] flex-col gap-2">
        <div className="text-[13px] text-slate-500">
          ATS match score{!finalized && session.changes.length > 0 ? " if you keep every change" : ""}
        </div>
        <div className="text-[22px] font-bold">
          {after >= 85 ? "Strong match" : after >= 70 ? "Good match" : "Needs work"}{" "}
          {gain > 0 && <span className="text-[15px] font-medium text-green-700">+{gain} from original</span>}
        </div>
        <p className="m-0 text-sm leading-relaxed text-slate-600">
          {session.aiEnabled
            ? "Score is computed by code from keyword coverage and title match, not by the AI."
            : "AI rewrites are off on this server, so only the keyword analysis is shown."}
        </p>
      </div>
      {finalized && (
        <div className="flex flex-col gap-2">
          <button type="button" onClick={() => open(session.pdfPath)} className={`${btnPrimary} cursor-pointer text-sm`}>
            Download PDF
          </button>
          <button type="button" onClick={() => open(session.docxPath)} className={`${btnSecondary} cursor-pointer text-sm`}>
            Download Word
          </button>
          {session.applicationId && (
            <Link to={`/applications/${session.applicationId}`} className="text-center text-[13px] font-medium">
              View application
            </Link>
          )}
        </div>
      )}
    </Card>
  );
}

function Keywords({ score }: { score: TailorScore }) {
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <h2 className="m-0 text-base font-semibold">Keywords</h2>
      {score.matched.length > 0 && (
        <KeywordGroup label="Matched">
          {score.matched.map((k) => <Chip key={k} tone="match">{k}</Chip>)}
        </KeywordGroup>
      )}
      {score.partial.length > 0 && (
        <KeywordGroup label="Different wording (ATS may miss these)">
          {score.partial.map((k) => <Chip key={k} tone="partial">{k}</Chip>)}
        </KeywordGroup>
      )}
      {score.missing.length > 0 && (
        <KeywordGroup label="Missing — add only if they reflect real experience">
          {score.missing.map((k) => <Chip key={k} tone="missing">{k}</Chip>)}
        </KeywordGroup>
      )}
    </Card>
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

const KIND_LABEL: Record<TailorChange["kind"], string> = {
  rewrite: "Rewrite",
  add_bullets: "Added from experience bank",
  add_entry: "Added from experience bank",
  remove: "Remove",
  reorder: "Reorder",
};

function ChangeRow({ change: c, decision, onChange }: {
  change: TailorChange;
  decision: Decision;
  onChange: (d: Decision) => void;
}) {
  const [editing, setEditing] = useState(false);
  const editable = c.kind === "rewrite" || c.kind === "add_bullets" || c.kind === "add_entry";
  const text = decision.action === "edit" ? decision.text ?? c.after : c.after;
  const rejected = decision.action === "reject";
  const lines = useMemo(() => text.split("\n").filter(Boolean), [text]);

  return (
    <div className={`flex flex-wrap items-start gap-5 border-t border-slate-100 px-5 py-4.5 first-of-type:border-t-0 ${rejected ? "opacity-60" : ""}`}>
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-2">
        <div className="text-xs font-semibold text-slate-500">
          {KIND_LABEL[c.kind]} · {[c.section, c.entry].filter(Boolean).join(" · ")}
        </div>

        {c.kind === "rewrite" && (
          <div className="text-sm leading-normal text-slate-400 line-through">{c.before}</div>
        )}
        {c.kind === "remove" && <div className="text-sm leading-normal text-slate-500 line-through">{c.before}</div>}

        {editing ? (
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {c.kind === "rewrite" ? "Edit rewrite" : "Edit bullets (one per line)"}
            <textarea
              autoFocus
              rows={c.kind === "rewrite" ? 3 : 4}
              value={text}
              onChange={(e) => onChange({ action: "edit", text: e.target.value })}
              className="rounded-lg border border-slate-300 p-2.5 text-sm text-slate-900 outline-none focus:border-blue-700"
            />
          </label>
        ) : c.kind === "rewrite" ? (
          <div className="text-sm leading-normal">{text}</div>
        ) : c.kind === "reorder" ? (
          <ol className="m-0 pl-5 text-sm leading-6 text-slate-700">
            {lines.map((l, i) => <li key={i}>{l}</li>)}
          </ol>
        ) : c.kind !== "remove" ? (
          <ul className="m-0 pl-5 text-sm leading-6 text-slate-800">
            {lines.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        ) : null}

        {c.reason && <div className="text-[13px] text-slate-500">{c.reason}</div>}
        {c.keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {c.keywords.map((k) => <Chip key={k} tone="match">{k}</Chip>)}
          </div>
        )}
        {c.warnings.map((w) => (
          <div key={w} className="rounded-md bg-amber-50 px-2.5 py-1.5 text-[13px] text-amber-800">{w}</div>
        ))}
      </div>

      <div className="flex gap-2">
        {editing ? (
          <button type="button" onClick={() => setEditing(false)} className={`${btnPrimary} min-h-10 cursor-pointer px-3.5 text-[13px]`}>
            Done
          </button>
        ) : (
          <>
            <button
              type="button"
              aria-pressed={!rejected}
              onClick={() => onChange(rejected ? { action: "accept" } : { action: "reject" })}
              className={
                rejected
                  ? `${btnSecondary} min-h-10 cursor-pointer px-3.5 text-[13px]`
                  : "inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-lg border border-green-700 bg-green-50 px-3.5 text-[13px] font-semibold text-green-700"
              }
            >
              {rejected ? "Keep" : (<><CheckIcon size={14} /> Kept</>)}
            </button>
            {rejected ? null : editable && (
              <button
                type="button"
                onClick={() => {
                  if (decision.action !== "edit") onChange({ action: "edit", text: c.after });
                  setEditing(true);
                }}
                className={`${btnSecondary} min-h-10 cursor-pointer px-3.5 text-[13px]`}
              >
                Edit
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Stepper({ status }: { status?: TailorStatus }) {
  const steps = ["Job details", "Tailoring", "Review", "Export"];
  const current = !status ? 1 : status === "running" || status === "needs_input" ? 2 : status === "review" || status === "error" ? 3 : 4;
  const done = status === "finalized";
  return (
    <ol aria-label="Progress" className="m-0 flex list-none flex-wrap gap-2 p-0 text-[13px]">
      {steps.map((label, i) => {
        const n = i + 1;
        const isDone = n < current || (done && n === current);
        const active = n === current && !isDone;
        const cls = isDone
          ? "bg-green-50 font-semibold text-green-700"
          : active
            ? "bg-blue-700 font-semibold text-white"
            : "bg-slate-100 font-medium text-slate-600";
        return (
          <li key={label} aria-current={active ? "step" : undefined} className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 ${cls}`}>
            {isDone ? <CheckIcon size={14} /> : `${n} ·`} {label}
          </li>
        );
      })}
    </ol>
  );
}
