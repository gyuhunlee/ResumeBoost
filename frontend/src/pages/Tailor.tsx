import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../lib/api";
import { fileUrl, listResumes, type Resume } from "../lib/resumes";
import {
  applyChanges,
  applyEdits,
  countDiffs,
  docKey,
  dropEditsFor,
  emptyEdits,
  hasEdits,
  indexDoc,
  keyTouchedBy,
  type Decision,
  type Decisions,
  type DocEdits,
} from "../lib/resumeDoc";
import { clearCache } from "../lib/store";
import type {
  FormatIssue,
  TailorAction,
  TailorAnswer,
  TailorChange,
  TailorScoreCheck,
  TailorSession,
  TailorStatus,
} from "../types";
import { CheckIcon, SparkleIcon } from "../components/Icons";
import ResumeEditor, { DEFAULT_STYLE } from "../components/ResumeEditor";
import { Card, Chip, ScoreRing, btnPrimary, btnSecondary } from "../components/ui";

const inputCls =
  "min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-blue-700 disabled:bg-slate-50 disabled:text-slate-500";
const labelCls = "flex flex-col gap-1.5 text-[13px] font-medium text-slate-700";
const POLL_MS = 2000;

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
  const reviewing = !!session && (status === "review" || status === "finalized");

  return (
    <div className="mx-auto flex max-w-[1280px] flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="m-0 text-[28px] font-bold tracking-tight">Tailor resume</h1>
        <Stepper status={status} />
      </div>

      {reviewing ? (
        <Review session={session!} onUpdated={setSession} onNew={reset} />
      ) : (
      <div className="flex flex-wrap items-start gap-6">
        <section aria-label="Job details" className="flex min-w-0 flex-[1_1_360px] flex-col gap-4">
          {session ? (
            <JobSummary session={session} onNew={reset} />
          ) : (
            <StartForm onStarted={started} />
          )}
          {status === "error" && session!.steps.length > 0 && <Activity session={session!} collapsible />}
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
      )}
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

function Activity({ session, collapsible = false }: { session: TailorSession; collapsible?: boolean }) {
  if (collapsible) {
    return (
      <Card className="p-5">
        <details>
          <summary className="cursor-pointer text-base font-semibold">Agent activity ({session.steps.length} steps)</summary>
          <div className="mt-3">
            <ActivityList session={session} />
          </div>
        </details>
      </Card>
    );
  }
  return (
    <Card className="flex flex-col gap-3 p-5">
      <h2 className="m-0 text-base font-semibold">Agent activity</h2>
      <ActivityList session={session} />
    </Card>
  );
}

function ActivityList({ session }: { session: TailorSession }) {
  return (
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
  const latest = session.steps.at(-1)?.summary;
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
      {latest && (
        <p className="m-0 flex items-center gap-2 text-sm text-slate-500" aria-live="polite">
          <span aria-hidden className="size-2 shrink-0 animate-pulse rounded-full bg-blue-600" />
          {latest}
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

// ---- Review: editable preview + score + changes ------------------------------------------

type ScoreCheck = { key: string; result: TailorScoreCheck };

function Review({ session, onUpdated, onNew }: {
  session: TailorSession;
  onUpdated: (s: TailorSession) => void;
  onNew: () => void;
}) {
  const original = session.original ?? null;
  const templates = session.templates ?? [];
  const [template, setTemplate] = useState(session.template ?? "classic");
  const style = templates.find((t) => t.id === template)?.style ?? session.style ?? DEFAULT_STYLE;
  const [decisions, setDecisions] = useState<Decisions>({});
  const [edits, setEdits] = useState<DocEdits>(emptyEdits);
  const [showChanges, setShowChanges] = useState(true);
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [check, setCheck] = useState<ScoreCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [exportedKey, setExportedKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initFor = useRef<string | null>(null);

  // Start every session with every change kept and no edits.
  useEffect(() => {
    if (initFor.current === session.id) return;
    initFor.current = session.id;
    setDecisions(Object.fromEntries(session.changes.map((c) => [c.id, { action: "accept" as const }])));
    setEdits(emptyEdits());
    setCheck(null);
    setExportedKey(null);
    setTemplate(session.template ?? "classic");
  }, [session.id, session.changes, session.template]);

  const base = useMemo(
    () => (original ? applyChanges(original, session.changes, decisions) : null),
    [original, session.changes, decisions],
  );
  const baseIndex = useMemo(() => (base ? indexDoc(base) : null), [base]);
  const doc = useMemo(() => (base ? applyEdits(base, edits) : null), [base, edits]);
  const key = useMemo(() => (doc ? docKey(doc) : ""), [doc]);
  const diffCount = useMemo(() => (original && doc ? countDiffs(original, doc) : 0), [original, doc]);
  const userKeys = useMemo(
    () => new Set([...Object.keys(edits.text), ...Object.values(edits.added).flat().map((b) => b.id)]),
    [edits],
  );

  // A finalized session reopened later: what's on screen is what was exported.
  useEffect(() => {
    if (session.status === "finalized" && exportedKey === null && key) setExportedKey(key + template);
  }, [session.status, exportedKey, key, template]);

  const pristine =
    !hasEdits(edits) && session.changes.every((c) => (decisions[c.id]?.action ?? "accept") === "accept");
  const fresh = !!check && check.key === key;
  const kept = session.changes.filter((c) => decisions[c.id]?.action !== "reject").length;
  const finalized = session.status === "finalized";
  const exportStale = finalized && exportedKey !== null && exportedKey !== key + template;

  function decide(c: TailorChange, d: Decision) {
    setDecisions((all) => ({ ...all, [c.id]: d }));
    setEdits((e) => dropEditsFor(e, c)); // typing on top of the old version no longer applies
  }

  function setAll(action: TailorAction) {
    setDecisions(Object.fromEntries(session.changes.map((c) => [c.id, { action }])));
    setEdits((e) => session.changes.reduce((acc, c) => dropEditsFor(acc, c), e));
  }

  function edit(fieldKey: string, text: string) {
    setFocusKey(null);
    setEdits((e) => {
      const owner = Object.entries(e.added).find(([, list]) => list.some((b) => b.id === fieldKey));
      const rest = Object.fromEntries(Object.entries(e.text).filter(([k]) => k !== fieldKey));
      if (owner) {
        const [entryId, list] = owner;
        if (!text.trim()) return { text: rest, added: { ...e.added, [entryId]: list.filter((b) => b.id !== fieldKey) } };
        return { ...e, text: { ...e.text, [fieldKey]: text } };
      }
      // Typed back to what the kept changes say: not an edit any more.
      if (baseIndex && text === (baseIndex.text.get(fieldKey) ?? "")) return { ...e, text: rest };
      return { ...e, text: { ...e.text, [fieldKey]: text } };
    });
  }

  function addLine(entryId: string) {
    const id = `${entryId}+u${Date.now().toString(36)}`;
    setEdits((e) => ({ ...e, added: { ...e.added, [entryId]: [...(e.added[entryId] ?? []), { id, text: "" }] } }));
    setFocusKey(id);
  }

  function restore(id: string) {
    if (edits.text[id] === "") {
      setEdits((e) => ({ ...e, text: Object.fromEntries(Object.entries(e.text).filter(([k]) => k !== id)) }));
      return;
    }
    const removal = session.changes.find((c) => c.kind === "remove" && c.targetId === id);
    if (removal) decide(removal, { action: "reject" });
  }

  function undoEdits() {
    setEdits(emptyEdits());
    setFocusKey(null);
  }

  async function runCheck() {
    if (!doc) return;
    setChecking(true);
    setCheckError(null);
    const k = key;
    try {
      setCheck({ key: k, result: await api.scoreTailor(session.id, doc) });
    } catch (err) {
      setCheckError(err instanceof Error ? err.message : "Couldn't check the score.");
    } finally {
      setChecking(false);
    }
  }

  async function create() {
    if (!doc) return;
    setBusy(true);
    setError(null);
    const k = key;
    try {
      const list = session.changes.map((c) => ({
        changeId: c.id,
        action: decisions[c.id]?.action ?? "accept",
        text: decisions[c.id]?.action === "edit" ? decisions[c.id]?.text ?? "" : null,
      }));
      onUpdated(await api.finalizeTailor(session.id, { decisions: list, document: doc, template }));
      setExportedKey(k + template);
      clearCache(); // Applications / Dashboard should refetch the new row
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the resume.");
    } finally {
      setBusy(false);
    }
  }

  const keywordScore = fresh ? check!.result : pristine ? session.projected ?? session.baseline : check?.result ?? session.projected ?? session.baseline;
  const formatIssues: FormatIssue[] = check ? check.result.formatIssues : session.formatIssues;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
      <section aria-label="Tailored resume" className="flex min-w-0 flex-col gap-3">
        {doc && original ? (
          <>
            <PreviewToolbar
              templates={templates.map((t) => ({ id: t.id, name: t.name }))}
              template={template}
              onTemplate={setTemplate}
              diffCount={diffCount}
              showChanges={showChanges}
              onToggle={() => setShowChanges((v) => !v)}
              edited={hasEdits(edits)}
              onUndo={undoEdits}
            />
            <div className="rounded-xl bg-slate-100 p-3 sm:p-6">
              <ResumeEditor
                doc={doc}
                original={original}
                style={style}
                showChanges={showChanges}
                userKeys={userKeys}
                focusKey={focusKey}
                onEdit={edit}
                onAddLine={addLine}
                onRestore={restore}
              />
            </div>
          </>
        ) : (
          <Card className="p-5 text-sm text-slate-600">
            This session was created before the live preview existed. Start a new one to edit the resume directly.
          </Card>
        )}
      </section>

      <aside aria-label="Score and changes" className="flex min-w-0 flex-col gap-4">
        <ScoreCard
          session={session}
          check={check}
          fresh={fresh}
          pristine={pristine}
          checking={checking}
          checkError={checkError}
          onCheck={runCheck}
          canCheck={!!doc}
        />

        <Card className="flex flex-col gap-3 p-5">
          <h2 className="m-0 text-base font-semibold">Export</h2>
          <p className="m-0 text-sm leading-relaxed text-slate-600">
            {finalized
              ? exportStale
                ? "You've changed the resume since the last export. Re-create to update the files."
                : formatModeText(session.formatMode, session.style?.source ?? "text")
              : "Creates a PDF and a Word file of the resume exactly as shown, and saves the job to Applications."}
          </p>
          <button
            type="button"
            onClick={create}
            disabled={busy || !doc}
            className={`${finalized && !exportStale ? btnSecondary : btnPrimary} cursor-pointer text-sm`}
          >
            {busy ? "Creating…" : finalized ? "Re-create resume" : "Create tailored resume"}
          </button>
          {finalized && (
            <div className="flex flex-wrap gap-2">
              <DownloadButton path={session.pdfPath} label="Download PDF" />
              <DownloadButton path={session.docxPath} label="Download Word" />
              {session.applicationId && (
                <Link to={`/applications/${session.applicationId}`} className="self-center text-[13px] font-medium">
                  View application
                </Link>
              )}
            </div>
          )}
          {error && <p role="alert" className="m-0 text-[13px] text-red-700">{error}</p>}
        </Card>

        {session.summary && (
          <Card className="flex gap-3 p-5">
            <SparkleIcon size={18} className="mt-0.5 shrink-0 text-blue-700" />
            <p className="m-0 text-sm leading-relaxed text-slate-700">{session.summary}</p>
          </Card>
        )}

        {session.changes.length > 0 && (
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
              <div>
                <h2 className="m-0 text-base font-semibold">Proposed changes</h2>
                <span className="text-[13px] text-slate-500" aria-live="polite">
                  {kept} of {session.changes.length} kept
                </span>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => setAll("accept")} className={`${btnSecondary} min-h-9 cursor-pointer px-3 text-[13px]`}>
                  Keep all
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
                overridden={Object.keys(edits.text).some((k) => keyTouchedBy(c, k))}
                onChange={(d) => decide(c, d)}
              />
            ))}
          </Card>
        )}

        {keywordScore && <Keywords score={keywordScore} />}

        {formatIssues.length > 0 && (
          <Card className="flex flex-col gap-2.5 p-5">
            <h2 className="m-0 text-base font-semibold">Format check</h2>
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {formatIssues.map((i, n) => (
                <li key={n} className="flex gap-2.5 text-sm leading-snug text-slate-700">
                  <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-full ${i.severity === "warning" ? "bg-amber-500" : "bg-slate-400"}`} />
                  {i.message}
                </li>
              ))}
            </ul>
          </Card>
        )}

        <JobSummary session={session} onNew={onNew} />
        {session.steps.length > 0 && <Activity session={session} collapsible />}
      </aside>
    </div>
  );
}

function formatModeText(mode: string | undefined, source: string): string {
  if (mode === "template") return "Saved to Applications. Both files use the template shown.";
  if (mode === "original") return "Saved to Applications. The Word file is your original document with only the text changed.";
  if (source === "pdf") return "Saved to Applications. Both files use the fonts, sizes and layout read from your PDF.";
  if (source === "docx") return "Saved to Applications. Your Word layout couldn't be edited in place, so both files were rebuilt in its fonts and layout.";
  return "Saved to Applications.";
}

function PreviewToolbar({ templates, template, onTemplate, diffCount, showChanges, onToggle, edited, onUndo }: {
  templates: { id: string; name: string }[];
  template: string;
  onTemplate: (id: string) => void;
  diffCount: number;
  showChanges: boolean;
  onToggle: () => void;
  edited: boolean;
  onUndo: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="m-0 text-base font-semibold">Tailored resume</h2>
        <p className="m-0 text-[13px] text-slate-500">
          Click any line to edit it. The PDF and Word files use the template you pick.
        </p>
      </div>
      {templates.length > 1 && (
        <div role="radiogroup" aria-label="Template" className="flex w-full flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[13px] font-medium text-slate-600">Template</span>
          {templates.map((t) => (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={template === t.id}
              onClick={() => onTemplate(t.id)}
              className={`min-h-9 cursor-pointer rounded-lg border px-3 text-[13px] font-semibold ${
                template === t.id
                  ? "border-blue-700 bg-blue-50 text-blue-700"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              {t.name}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[13px] text-slate-600" aria-live="polite">
          {diffCount === 0 ? "Same as original" : `${diffCount} line${diffCount === 1 ? "" : "s"} changed`}
        </span>
        {edited && (
          <button type="button" onClick={onUndo} className={`${btnSecondary} min-h-9 cursor-pointer px-3 text-[13px]`}>
            Undo my edits
          </button>
        )}
        <button
          type="button"
          role="switch"
          aria-checked={showChanges}
          onClick={onToggle}
          className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg px-1 text-[13px] font-medium text-slate-700"
        >
          <span
            aria-hidden
            className={`relative h-5 w-9 rounded-full transition-colors ${showChanges ? "bg-blue-700" : "bg-slate-300"}`}
          >
            <span className={`absolute top-0.5 size-4 rounded-full bg-white shadow transition-all ${showChanges ? "left-4.5" : "left-0.5"}`} />
          </span>
          Highlight changes
        </button>
      </div>
      {showChanges && (
        <div className="flex w-full flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600" aria-label="Highlight legend">
          <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-3 rounded-sm bg-emerald-100 ring-1 ring-emerald-300" />AI change</span>
          <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-3 rounded-sm bg-blue-100 ring-1 ring-blue-300" />Your edit</span>
          <span className="inline-flex items-center gap-1.5"><del className="text-red-700 decoration-red-500">Removed</del></span>
        </div>
      )}
    </div>
  );
}

function DownloadButton({ path, label }: { path?: string | null; label: string }) {
  if (!path) return null;
  return (
    <button
      type="button"
      onClick={async () => window.open(await fileUrl(path), "_blank", "noopener")}
      className={`${btnSecondary} min-h-10 cursor-pointer px-4 text-sm`}
    >
      {label}
    </button>
  );
}

function ScoreCard({ session, check, fresh, pristine, checking, checkError, onCheck, canCheck }: {
  session: TailorSession;
  check: ScoreCheck | null;
  fresh: boolean;
  pristine: boolean;
  checking: boolean;
  checkError: string | null;
  onCheck: () => void;
  canCheck: boolean;
}) {
  const before = session.baseline?.score ?? 0;
  const projected = session.projected?.score ?? before;

  let value: number;
  let caption: string;
  let stale = false;
  if (fresh) {
    value = check!.result.score;
    caption = "Your version, as edited";
  } else if (pristine) {
    value = projected;
    caption = session.changes.length > 0 ? "If you keep every change" : "Your resume";
  } else {
    value = check?.result.score ?? projected;
    stale = true;
    caption = "Out of date: you've changed the resume since this score";
  }
  const gain = value - before;

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-center gap-5">
        <div className={stale ? "opacity-45" : ""}>
          <ScoreRing value={value} size={96} />
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <div className="text-[13px] text-slate-500">ATS match score</div>
          <div className="text-lg font-bold">
            {value >= 85 ? "Strong match" : value >= 70 ? "Good match" : "Needs work"}
          </div>
          {gain !== 0 && (
            <div className={`text-[13px] font-medium ${gain > 0 ? "text-green-700" : "text-red-700"}`}>
              {gain > 0 ? "+" : ""}{gain} from original
            </div>
          )}
          <div className={`text-[13px] ${stale ? "font-medium text-amber-700" : "text-slate-500"}`} aria-live="polite">
            {caption}
          </div>
        </div>
      </div>

      <dl className="m-0 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center">
        {[
          ["Original", String(before)],
          ["AI version", String(projected)],
          ["Your version", fresh ? String(check!.result.score) : check ? `${check.result.score}*` : "—"],
        ].map(([label, v]) => (
          <div key={label}>
            <dt className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">{label}</dt>
            <dd className="m-0 text-lg font-bold text-slate-900">{v}</dd>
          </div>
        ))}
      </dl>

      <button
        type="button"
        onClick={onCheck}
        disabled={checking || fresh || !canCheck}
        className={`${stale ? btnPrimary : btnSecondary} cursor-pointer text-sm disabled:cursor-default`}
      >
        {checking ? "Checking…" : fresh ? (<><CheckIcon size={16} /> Score is up to date</>) : check ? "Recheck ATS score" : "Check ATS score"}
      </button>
      {checkError && <p role="alert" className="m-0 text-[13px] text-red-700">{checkError}</p>}
      <p className="m-0 text-xs leading-relaxed text-slate-500">
        {check && !fresh ? "* from your last check, before your latest changes. " : ""}
        {session.aiEnabled
          ? "Scored by code, not by the AI: 85% keyword coverage (required skills count 3×), 15% job-title match."
          : "AI rewrites are off on this server, so only the keyword analysis is shown."}
      </p>
    </Card>
  );
}

function Keywords({ score }: { score: { matched: string[]; partial: string[]; missing: string[] } }) {
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

function ChangeRow({ change: c, decision, overridden, onChange }: {
  change: TailorChange;
  decision: Decision;
  /** The user typed over this change in the preview. */
  overridden: boolean;
  onChange: (d: Decision) => void;
}) {
  const [editing, setEditing] = useState(false);
  const editable = c.kind === "rewrite" || c.kind === "add_bullets" || c.kind === "add_entry";
  const text = decision.action === "edit" ? decision.text ?? c.after : c.after;
  const rejected = decision.action === "reject";
  const lines = useMemo(() => text.split("\n").filter(Boolean), [text]);

  return (
    <div className={`flex flex-wrap items-start gap-3 border-t border-slate-100 px-5 py-4 first-of-type:border-t-0 ${rejected ? "opacity-60" : ""}`}>
      <div className="flex min-w-0 flex-[1_1_260px] flex-col gap-2">
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

        {overridden && !rejected && (
          <div className="w-fit rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-800">Edited in the preview</div>
        )}
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
