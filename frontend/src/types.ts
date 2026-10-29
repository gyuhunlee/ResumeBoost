// Shared shapes. These mirror the Pydantic models in backend/app/schemas.py.

export type ApplicationStatus =
  | "applied"
  | "interviewing"
  | "offer"
  | "follow_up"
  | "rejected";

export type ApplicationSource = "tailored" | "gmail" | "both";

export interface Application {
  id: string;
  company: string;
  role: string;
  /** null = tailored here, but no email has confirmed it was submitted yet (row shows greyed out). */
  status: ApplicationStatus | null;
  /** null when the resume wasn't tailored on this site. */
  atsScore: number | null;
  /** ISO 8601 date-time (with offset) of the email that last changed the status. */
  lastUpdateAt: string | null;
  source: ApplicationSource;
  /** false disables "Download PDF". */
  hasTailoredResume: boolean;
  /** An email was matched to this application without certainty. */
  needsReview: boolean;
}

export type EmailEventType = "applied" | "interviewing" | "offer" | "rejected";

export interface EmailEvent {
  id: string;
  type: EmailEventType;
  subject: string;
  sender: string;
  receivedAt: string; // ISO 8601 date-time
  interviewAt?: string | null;
}

export interface ApplicationDetail extends Application {
  jobDescription: string | null;
  tailoredResumePath: string | null;
  appliedAt: string | null;
  createdAt: string;
  updatedAt: string;
  emails: EmailEvent[];
}

export interface GmailStatus {
  connected: boolean;
  gmailAddress?: string | null;
  lastSyncedAt?: string | null;
  syncStatus?: "idle" | "running" | "error" | null;
  lastError?: string | null;
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
  /** false for previews, so they don't create an application. Defaults to true. */
  save?: boolean;
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
  applicationId?: string | null;
}
