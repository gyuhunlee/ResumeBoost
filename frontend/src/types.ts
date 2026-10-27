// Shared shapes. These mirror the Pydantic models in backend/app/schemas.py.

export type ApplicationStatus =
  | "applied"
  | "interviewing"
  | "offer"
  | "follow_up"
  | "rejected";

export interface Application {
  id: string;
  company: string;
  role: string;
  status: ApplicationStatus;
  atsScore: number;
  lastUpdateAt: string; // ISO date "YYYY-MM-DD" of the latest email for this application
}

export interface ApplicationStats {
  applied: number;
  interviewing: number;
  offers: number;
  followUpsDue: number;
}

/** Number of applications currently in each status (drives the dashboard ring). */
export type StatusCounts = Record<ApplicationStatus, number>;

/** Something that happened or will happen on a given day (an email, an interview, a deadline). */
export interface CalendarEvent {
  id: string;
  date: string; // ISO date "YYYY-MM-DD"
  time?: string | null; // "HH:MM", 24h, local to the user
  kind: ApplicationStatus; // decides the dot color
  title: string; // e.g. "Interview · Northwind"
  detail: string; // e.g. "Software Engineer"
}

/** An upcoming item shown in the dashboard's notification panel. */
export interface Reminder {
  id: string;
  date: string; // ISO date "YYYY-MM-DD"
  time?: string | null; // "HH:MM", 24h
  kind: "interviewing" | "follow_up" | "offer";
  company: string;
  role: string;
  message: string;
}

export interface DashboardData {
  counts: StatusCounts;
  events: CalendarEvent[];
  reminders: Reminder[];
}

export interface Rewrite {
  id: string;
  section: string;
  before: string;
  after: string;
}

export interface TailorRequest {
  company: string;
  role: string;
  jobDescription: string;
}

export interface TailorResult {
  originalScore: number;
  score: number;
  matchedKeywords: string[];
  missingKeywords: string[];
  rewrites: Rewrite[];
  companyBrief: {
    summary: string;
    highlights: string[];
  };
}
