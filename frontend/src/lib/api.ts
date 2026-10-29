import type {
  Application,
  ApplicationDetail,
  ApplicationStats,
  GmailStatus,
  DashboardData,
  TailorRequest,
  TailorResult,
} from "../types";
import { supabase } from "./supabase";

// Empty in dev (Vite proxies /api), your Render/Cloud Run URL in production.
const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (data.session) headers.set("Authorization", `Bearer ${data.session.access_token}`);
  // Let the browser set the multipart boundary for file uploads
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// The dashboard groups emails by day, so the server needs the user's time zone.
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

export const api = {
  listApplications: () =>
    request<{ stats: ApplicationStats; items: Application[] }>(
      "/api/applications",
    ),
  getApplication: (id: string) =>
    request<ApplicationDetail>(`/api/applications/${encodeURIComponent(id)}`),
  getDashboard: () =>
    request<DashboardData>(`/api/dashboard?tz=${encodeURIComponent(timeZone)}`),

  gmailStatus: () => request<GmailStatus>("/api/gmail/status"),
  gmailConnectUrl: () => request<{ url: string }>("/api/gmail/connect-url"),
  gmailSync: () => request<GmailStatus>("/api/gmail/sync", { method: "POST" }),
  gmailDisconnect: () => request<void>("/api/gmail", { method: "DELETE" }),

  deleteAccount: () => request<void>("/api/account", { method: "DELETE" }),

  tailor: (body: TailorRequest) =>
    request<TailorResult>("/api/tailor", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  extractResumeText: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ text: string }>("/api/resumes/extract", { method: "POST", body });
  },
};

