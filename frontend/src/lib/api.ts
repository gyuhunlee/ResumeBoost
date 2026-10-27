import type {
  Application,
  ApplicationStats,
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
  return res.json() as Promise<T>;
}

export const api = {
  listApplications: () =>
    request<{ stats: ApplicationStats; items: Application[] }>(
      "/api/applications",
    ),
  getDashboard: () => request<DashboardData>("/api/dashboard"),
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

