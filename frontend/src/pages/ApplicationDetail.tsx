import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { api } from "../lib/api";
import { fileUrl } from "../lib/resumes";
import { formatDateTime } from "../lib/dates";
import { mockApplications } from "../data/mock";
import type { ApplicationDetail as Detail, EmailEvent } from "../types";
import { ChevronLeftIcon, DocIcon } from "../components/Icons";
import { Card, ScoreBar, StatusPill, btnPrimary, btnSecondary } from "../components/ui";

const SOURCE_LABEL: Record<Detail["source"], string> = {
  tailored: "Tailored on Resumeboost · not confirmed by email yet",
  gmail: "Found in your Gmail",
  both: "Tailored on Resumeboost · confirmed by email",
};

const EMAIL_LABEL: Record<EmailEvent["type"], string> = {
  applied: "Application received",
  interviewing: "Interview / next steps",
  offer: "Offer",
  rejected: "Not moving forward",
};

export default function ApplicationDetail() {
  const { id = "" } = useParams();
  const [app, setApp] = useState<Detail | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "sample">("loading");
  const [pdfError, setPdfError] = useState<string | null>(null);

  useEffect(() => {
    setState("loading");
    api
      .getApplication(id)
      .then((d) => {
        setApp(d);
        setState("ready");
      })
      .catch((e: Error) => {
        // Backend offline: show the sample row if this id is one of them.
        const sample = mockApplications.find((a) => a.id === id);
        if (sample && !e.message.includes("not found")) {
          setApp({ ...sample, jobDescription: null, tailoredResumePath: null, appliedAt: sample.lastUpdateAt,
                   createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), emails: [] });
          setState("sample");
        } else {
          setState("missing");
        }
      });
  }, [id]);

  async function downloadPdf() {
    if (!app?.tailoredResumePath) return;
    setPdfError(null);
    try {
      window.open(await fileUrl(app.tailoredResumePath), "_blank", "noopener");
    } catch {
      setPdfError("Couldn't get the PDF. Try again.");
    }
  }

  const back = (
    <Link to="/applications" className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-slate-600 no-underline hover:text-slate-900">
      <ChevronLeftIcon size={16} />
      Applications
    </Link>
  );

  if (state === "loading") return <div className="mx-auto max-w-4xl">{back}<p className="text-slate-500">Loading…</p></div>;
  if (state === "missing" || !app) {
    return (
      <div className="mx-auto max-w-4xl">
        {back}
        <Card className="mt-4 p-8 text-center text-slate-600">This application doesn't exist or was deleted.</Card>
      </div>
    );
  }

  const canDownload = app.hasTailoredResume && !!app.tailoredResumePath;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div>
        {back}
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="m-0 text-[28px] font-bold tracking-tight">{app.company}</h1>
            <p className="mt-1 mb-0 text-[15px] text-slate-600">
              {app.role || "Role not stated"}
              {state === "sample" && <span className="ml-2 text-slate-500">(sample data)</span>}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={downloadPdf}
              disabled={!canDownload}
              title={canDownload ? undefined : "Only available for resumes tailored on Resumeboost"}
              className={`${btnPrimary} cursor-pointer text-sm disabled:cursor-not-allowed disabled:bg-slate-300 disabled:opacity-100`}
            >
              <DocIcon size={16} />
              Download PDF
            </button>
          </div>
        </div>
        {!app.hasTailoredResume && (
          <p className="mt-2 mb-0 text-right text-[13px] text-slate-500">
            This job was found in your inbox, so there's no tailored resume to download.
          </p>
        )}
        {pdfError && <p role="alert" className="mt-2 mb-0 text-right text-sm text-red-700">{pdfError}</p>}
      </div>

      {app.needsReview && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          An email was matched to this application, but the company has several applications with similar roles.
          Check the emails below to confirm they belong here.
        </div>
      )}

      <Card className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-5 p-6">
        <Field label="Status">{app.status ? <StatusPill status={app.status} /> : <Dash />}</Field>
        <Field label="ATS match">
          {app.atsScore === null ? <Dash /> : (
            <div className="flex items-center gap-2.5">
              <ScoreBar value={app.atsScore} className="w-20" />
              <span className="font-semibold">{app.atsScore}</span>
            </div>
          )}
        </Field>
        <Field label="Applied">{app.appliedAt ? <DateTime iso={app.appliedAt} /> : <Dash />}</Field>
        <Field label="Status updated">{app.lastUpdateAt ? <DateTime iso={app.lastUpdateAt} /> : <Dash />}</Field>
        <Field label="Source"><span className="text-sm text-slate-700">{SOURCE_LABEL[app.source]}</span></Field>
      </Card>

      <Card className="p-6">
        <h2 className="m-0 text-lg font-semibold">Emails</h2>
        {app.emails.length === 0 ? (
          <p className="mt-2 mb-0 text-sm text-slate-500">
            {app.source === "tailored"
              ? "No emails yet. When the confirmation arrives in Gmail, this application will update automatically."
              : "No emails linked yet."}
          </p>
        ) : (
          <ol className="mt-4 mb-0 flex list-none flex-col gap-4 p-0">
            {app.emails.map((e) => (
              <li key={e.id} className="flex flex-col gap-1 border-l-2 border-slate-200 pl-4">
                <div className="flex flex-wrap items-center gap-2 text-[13px] text-slate-500">
                  <span className="font-semibold text-slate-700">{EMAIL_LABEL[e.type]}</span>
                  · <DateTime iso={e.receivedAt} />
                </div>
                <div className="text-sm font-medium text-slate-900">{e.subject || "(no subject)"}</div>
                <div className="text-[13px] text-slate-500">{e.sender}</div>
                {e.interviewAt && (
                  <div className="text-[13px] font-semibold text-blue-700">
                    Interview: <DateTime iso={e.interviewAt} />
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="m-0 text-lg font-semibold">Job description</h2>
        {app.jobDescription ? (
          <details className="mt-3">
            <summary className={`${btnSecondary} min-h-9 cursor-pointer px-3.5 text-[13px]`}>Show job description</summary>
            <p className="mt-3 mb-0 text-sm leading-relaxed whitespace-pre-wrap text-slate-700">{app.jobDescription}</p>
          </details>
        ) : (
          <p className="mt-2 mb-0 text-sm text-slate-500">
            Not available. Job descriptions are saved when you tailor a resume here.
          </p>
        )}
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[13px] text-slate-500">{label}</div>
      <div>{children}</div>
    </div>
  );
}

const Dash = () => <span className="text-slate-400" aria-label="Unknown">–</span>;

const DateTime = ({ iso }: { iso: string }) => (
  <time dateTime={iso} className="text-sm text-slate-700">{formatDateTime(iso)}</time>
);
