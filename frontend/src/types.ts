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
  lastUpdate: string; // e.g. "Interview invite · Today" (derived from Gmail)
}

export interface ApplicationStats {
  applied: number;
  interviewing: number;
  offers: number;
  followUpsDue: number;
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
