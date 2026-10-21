import type {
  Application,
  ApplicationStats,
  TailorRequest,
  TailorResult,
} from "../types";

// Empty in dev (Vite proxies /api), your Render/Cloud Run URL in production.
const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listApplications: () =>
    request<{ stats: ApplicationStats; items: Application[] }>(
      "/api/applications",
    ),
  tailor: (body: TailorRequest) =>
    request<TailorResult>("/api/tailor", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
