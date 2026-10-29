import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";
import { supabase } from "../lib/supabase";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/dates";
import { useGmailSync } from "../lib/useGmailSync";
import { useAuth } from "../auth/AuthProvider";
import { Card, btnPrimary, btnSecondary } from "../components/ui";
import { deleteResume, fileUrl, listResumes, saveResume, uploadResume, type Resume } from "../lib/resumes";

const inputCls =
  "min-h-10 rounded-lg border border-slate-300 px-3 text-sm text-slate-900 outline-none focus:border-blue-700";
const labelCls = "flex flex-col gap-1.5 text-[13px] font-medium text-slate-700";
const MAX_BYTES = 5 * 1024 * 1024;

export default function Settings() {
  const { session } = useAuth();
  const user = session!.user; // RequireAuth guarantees a session here
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="m-0 text-[28px] font-bold tracking-tight">Settings</h1>
      <AccountCard userId={user.id} email={user.email ?? ""} />
      <ResumesCard userId={user.id} />
      <GmailCard />
      <DeleteAccountCard userId={user.id} />
    </div>
  );
}

function AccountCard({ userId, email }: { userId: string; email: string }) {
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    supabase.from("profiles").select("full_name").eq("id", userId).single()
      .then(({ data }) => setName(data?.full_name ?? ""));
  }, [userId]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setStatus("saving");
    const { error } = await supabase.from("profiles").update({ full_name: name.trim() }).eq("id", userId);
    setStatus(error ? "error" : "saved");
  }

  return (
    <Card className="p-6">
      <form onSubmit={save} className="flex flex-col gap-4">
        <h2 className="m-0 text-lg font-semibold">Account</h2>
        <label className={labelCls}>
          Email
          <input className={`${inputCls} bg-slate-50 text-slate-600`} value={email} readOnly />
          <span className="text-xs font-normal text-slate-500">From your Google account.</span>
        </label>
        <label className={labelCls}>
          Name
          <input
            className={inputCls}
            value={name}
            required
            maxLength={100}
            onChange={(e) => { setName(e.target.value); setStatus("idle"); }}
          />
        </label>
        <div className="flex items-center gap-3">
          <button type="submit" disabled={status === "saving"} className={`${btnPrimary} cursor-pointer text-sm`}>
            {status === "saving" ? "Saving…" : "Save"}
          </button>
          <span aria-live="polite" className="text-[13px] text-slate-500">
            {status === "saved" && "Saved"}
            {status === "error" && "Couldn't save. Try again."}
          </span>
        </div>
      </form>
    </Card>
  );
}

function ResumesCard({ userId }: { userId: string }) {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listResumes().then(setResumes).catch((e: Error) => setError(e.message));
  }, []);

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow picking the same file again
    if (!file) return;
    if (file.size > MAX_BYTES) return setError("Files must be 5 MB or smaller.");
    setBusy(true);
    setError(null);
    try {
      const created = await uploadResume(userId, file);
      setResumes((rs) => [created, ...rs]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-semibold">Resumes</h2>
          <p className="mt-1 mb-0 text-sm text-slate-600">
            Upload a PDF or DOCX. The text is extracted so you can edit it before tailoring.
          </p>
        </div>
        <label className={`${btnPrimary} cursor-pointer text-sm`}>
          {busy ? "Uploading…" : "Upload resume"}
          <input type="file" accept=".pdf,.docx" className="sr-only" disabled={busy} onChange={onFile} />
        </label>
      </div>

      {error && <p role="alert" className="m-0 text-sm text-red-700">{error}</p>}
      {resumes.length === 0 && !busy && <p className="m-0 text-sm text-slate-500">No resumes yet.</p>}

      {resumes.map((r) => (
        <ResumeItem
          key={r.id}
          resume={r}
          onSaved={(u) => setResumes((rs) => rs.map((x) => (x.id === u.id ? u : x)))}
          onDeleted={() => setResumes((rs) => rs.filter((x) => x.id !== r.id))}
        />
      ))}
    </Card>
  );
}

function ResumeItem({ resume, onSaved, onDeleted }: {
  resume: Resume;
  onSaved: (r: Resume) => void;
  onDeleted: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(resume.title);
  const [content, setContent] = useState(resume.content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      onSaved(await saveResume(resume.id, { title: title.trim() || "My resume", content }));
      setEditing(false);
    } catch {
      setError("Couldn't save. Try again.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${resume.title}"?`)) return;
    try { await deleteResume(resume); onDeleted(); }
    catch { setError("Couldn't delete. Try again."); }
  }

  async function openFile() {
    if (resume.file_path) window.open(await fileUrl(resume.file_path), "_blank", "noopener");
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4">
      {editing ? (
        <>
          <label className={labelCls}>
            Title
            <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className={labelCls}>
            Resume text
            <textarea
              rows={16}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="resize-y rounded-lg border border-slate-300 p-3 font-mono text-[13px] leading-relaxed outline-none focus:border-blue-700"
            />
          </label>
          <div className="flex gap-2">
            <button type="button" onClick={save} disabled={saving} className={`${btnPrimary} cursor-pointer text-sm`}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => { setTitle(resume.title); setContent(resume.content); setEditing(false); }}
              className={`${btnSecondary} cursor-pointer text-sm`}
            >
              Cancel
            </button>
          </div>
        </>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-semibold">{resume.title}</div>
            <div className="text-[13px] text-slate-500">
              {resume.file_name} · updated {new Date(resume.updated_at).toLocaleDateString()}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {resume.file_path && (
              <button type="button" onClick={openFile} className={`${btnSecondary} cursor-pointer text-sm`}>View file</button>
            )}
            <button type="button" onClick={() => setEditing(true)} className={`${btnSecondary} cursor-pointer text-sm`}>Edit</button>
            <button type="button" onClick={remove} className={`${btnSecondary} cursor-pointer text-sm text-red-700`}>Delete</button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="m-0 text-sm text-red-700">{error}</p>}
    </div>
  );
}
const GMAIL_RESULT: Record<string, { text: string; ok: boolean }> = {
  connected: { text: "Gmail connected. Your first sync is running.", ok: true },
  cancelled: { text: "Gmail wasn't connected.", ok: false },
  error: { text: "Couldn't connect Gmail. Try again.", ok: false },
};

function GmailCard() {
  const location = useLocation();
  const navigate = useNavigate();
  // Google sends the user back to /settings?gmail=connected|cancelled|error
  const [result] = useState(() => GMAIL_RESULT[new URLSearchParams(location.search).get("gmail") ?? ""]);
  const sync = useGmailSync(undefined, { autoSync: false });
  const { status, error, syncing } = sync;

  useEffect(() => {
    if (location.search.includes("gmail=")) navigate({ search: "", hash: "gmail" }, { replace: true });
    if (location.hash === "#gmail") document.getElementById("gmail")?.scrollIntoView({ behavior: "smooth" });
    // Poll after connecting so "Last synced" fills in when the first sync ends.
    if (result?.ok) void sync.syncNow();
  }, []);

  async function disconnect() {
    if (!window.confirm("Disconnect Gmail? Applications already found stay on your account.")) return;
    await sync.disconnect();
  }

  return (
    <Card className="flex scroll-mt-6 flex-col gap-4 p-6">
      <div id="gmail" className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-xl">
          <h2 className="m-0 text-lg font-semibold">Gmail</h2>
          <p className="mt-1 mb-0 text-sm text-slate-600">
            Resumeboost reads emails from applicant tracking systems (confirmations, interview invites,
            rejections) to build your Applications list. It has read-only access, only looks at mail received
            after you signed up, and never stores email bodies.
          </p>
        </div>
        {status?.connected ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={sync.syncNow} disabled={syncing} className={`${btnSecondary} cursor-pointer text-sm`}>
              {syncing ? "Syncing…" : "Sync now"}
            </button>
            <button type="button" onClick={disconnect} className={`${btnSecondary} cursor-pointer text-sm text-red-700`}>
              Disconnect
            </button>
          </div>
        ) : (
          <button type="button" onClick={sync.connect} disabled={!status} className={`${btnPrimary} cursor-pointer text-sm`}>
            Connect Gmail
          </button>
        )}
      </div>

      {result && (
        <p role="status" className={`m-0 text-sm ${result.ok ? "text-green-700" : "text-red-700"}`}>{result.text}</p>
      )}
      {status?.connected && (
        <dl className="m-0 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
          <dt className="text-slate-500">Account</dt>
          <dd className="m-0">{status.gmailAddress}</dd>
          <dt className="text-slate-500">Last synced</dt>
          <dd className="m-0" aria-live="polite">
            {syncing ? "Syncing now…" : status.lastSyncedAt ? formatDateTime(status.lastSyncedAt) : "Not yet"}
          </dd>
          {status.syncStatus === "error" && !syncing && (
            <>
              <dt className="text-slate-500">Problem</dt>
              <dd className="m-0 text-red-700">
                {status.lastError}
                {status.lastError?.startsWith("Reconnect") && (
                  <button type="button" onClick={sync.connect} className="ml-2 cursor-pointer font-semibold text-blue-700">
                    Reconnect
                  </button>
                )}
              </dd>
            </>
          )}
        </dl>
      )}
      {!status && <p className="m-0 text-sm text-slate-500">Gmail status is unavailable while the server is offline.</p>}
      {error && <p role="alert" className="m-0 text-sm text-red-700">{error}</p>}
    </Card>
  );
}

const CONFIRM_WORD = "DELETE";

function DeleteAccountCard({ userId }: { userId: string }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove(e: FormEvent) {
    e.preventDefault();
    if (typed !== CONFIRM_WORD) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteAccount();
    } catch (err) {
      setBusy(false);
      return setError(err instanceof Error ? err.message : "Couldn't delete your account. Try again.");
    }
    // The server already removed the user, so only clear this browser's session.
    try {
      localStorage.removeItem(`rb:dismissed-reminders:${userId}`);
    } catch {
      /* storage unavailable */
    }
    await supabase.auth.signOut({ scope: "local" });
    navigate("/", { replace: true });
  }

  return (
    <Card className="flex flex-col gap-4 border-red-200 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-xl">
          <h2 className="m-0 text-lg font-semibold text-red-800">Delete account</h2>
          <p className="mt-1 mb-0 text-sm text-slate-600">
            Permanently deletes your account, resumes, tailored resumes, applications and email history,
            and removes Resumeboost's access to your Gmail. This can't be undone.
          </p>
        </div>
        {!open && (
          <button type="button" onClick={() => setOpen(true)} className={`${btnSecondary} cursor-pointer text-sm text-red-700`}>
            Delete account…
          </button>
        )}
      </div>

      {open && (
        <form onSubmit={remove} className="flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
          <label className={labelCls}>
            Type {CONFIRM_WORD} to confirm
            <input
              className={`${inputCls} bg-white`}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              autoFocus
              aria-describedby="delete-help"
            />
          </label>
          <span id="delete-help" className="sr-only">This permanently deletes your account.</span>
          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={typed !== CONFIRM_WORD || busy}
              className="inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg bg-red-700 px-5 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? "Deleting…" : "Permanently delete my account"}
            </button>
            <button
              type="button"
              onClick={() => { setOpen(false); setTyped(""); setError(null); }}
              disabled={busy}
              className={`${btnSecondary} cursor-pointer text-sm`}
            >
              Cancel
            </button>
          </div>
          {error && <p role="alert" className="m-0 text-sm text-red-700">{error}</p>}
        </form>
      )}
    </Card>
  );
}
