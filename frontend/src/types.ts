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
  /** Returned by "Sync now": how many emails changed an application. */
  changed?: number | null;
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
  /** A scheduled interview. Only these get a dot on the calendar grid. */
  scheduled?: boolean;
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

// ---- Resume tailoring agent (mirror backend/app/schemas.py) ----

export type TailorStatus = "running" | "needs_input" | "review" | "finalized" | "error";
export type TailorChangeKind = "rewrite" | "add_bullets" | "add_entry" | "remove" | "reorder";

export interface TailorStep {
  tool: string;
  summary: string;
  at: string;
}

export interface TailorQuestion {
  id: string;
  question: string;
  keyword: string;
  answered: boolean;
}

export interface TailorScore {
  score: number;
  matched: string[];
  /** Present only as a synonym ("Postgres" for "PostgreSQL"). */
  partial: string[];
  missing: string[];
}

export interface TailorChange {
  id: string;
  kind: TailorChangeKind;
  section: string;
  entry: string;
  before: string;
  after: string;
  keywords: string[];
  reason: string;
  /** Soft warnings from the claim checker, e.g. a name that isn't in the original resume. */
  warnings: string[];
  /** Bullet / entry / section id in the original resume that the change applies to. */
  targetId: string;
  /** add_bullets: {bullets}, add_entry: {entry, position}, reorder: {order}. */
  payload: Record<string, unknown>;
}

export interface FormatIssue {
  severity: "warning" | "info";
  message: string;
  targetId?: string | null;
}

export interface TailorSession {
  id: string;
  status: TailorStatus;
  company: string;
  role: string;
  error?: string | null;
  aiEnabled: boolean;
  jobTitle: string;
  steps: TailorStep[];
  questions: TailorQuestion[];
  baseline?: TailorScore | null;
  /** Score if every change is accepted. */
  projected?: TailorScore | null;
  changes: TailorChange[];
  formatIssues: FormatIssue[];
  summary: string;
  finalScore?: number | null;
  applicationId?: string | null;
  pdfPath?: string | null;
  docxPath?: string | null;
  /** Parsed original resume; the preview is rebuilt from it + the changes. Absent while running. */
  original?: ResumeDoc | null;
  /** Look of the uploaded file (fonts, sizes, alignment). */
  style?: ResumeStyle | null;
  /** Last export: "original" = your .docx edited in place, "matched" = rebuilt like your upload, "template". */
  formatMode?: string;
  /** Looks to choose from: Classic, Modern, and "Like my upload" when it could be read. */
  templates?: TemplateOption[];
  /** Template to show first (the last one exported, else Classic). */
  template?: string;
}

export interface TemplateOption {
  id: string;
  name: string;
  style: ResumeStyle;
}

export interface TailorScoreCheck {
  score: number;
  keywordCoverage: number;
  titleAlignment: number;
  matched: string[];
  partial: string[];
  missing: string[];
  formatIssues: FormatIssue[];
}

// ---- Structured resume (mirror backend/app/tailor/models.py and style.py) ----

export type ResumeSectionKind = "summary" | "experience" | "projects" | "education" | "skills" | "other";

export interface ResumeBullet {
  id: string;
  text: string;
}

export interface ResumeEntry {
  id: string;
  heading: string;
  subheading: string;
  dates: string;
  bullets: ResumeBullet[];
}

export interface ResumeSection {
  id: string;
  title: string;
  kind: ResumeSectionKind;
  entries: ResumeEntry[];
}

export interface ResumeDoc {
  name: string;
  contact: string[];
  sections: ResumeSection[];
}

export interface ResumeStyle {
  source: "pdf" | "docx" | "text";
  font: "serif" | "sans";
  fontName: string;
  nameSize: number;
  headingSize: number;
  bodySize: number;
  nameAlign: "left" | "center";
  headingBold: boolean;
  headingUpper: boolean;
  headingRule: boolean;
  headingColor: string;
  dateAlign: "right" | "inline";
  bullet: string;
  contactSep: string;
  /** inches */
  marginX: number;
  marginY: number;
}

export interface TailorStartRequest {
  company: string;
  role: string;
  jobDescription: string;
  resumeId?: string | null;
}

export interface TailorAnswer {
  questionId: string;
  /** null = skipped */
  confirmed: boolean | null;
  detail: string;
}

export type TailorAction = "accept" | "reject" | "edit";

export interface TailorDecision {
  changeId: string;
  action: TailorAction;
  text?: string | null;
}

export interface TailorFinalizeRequest {
  decisions: TailorDecision[];
  /** The resume exactly as shown in the editable preview. */
  document: ResumeDoc;
  /** Template id the files are rendered with. */
  template: string;
}
