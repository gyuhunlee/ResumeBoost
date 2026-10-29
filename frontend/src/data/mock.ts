import type { Application, ApplicationStats, DashboardData, TailorResult } from "../types";
import { addDays, toISODate } from "../lib/dates";

// Sample data used when the backend isn't running, so the UI still renders.
// The backend returns the same shapes from backend/app/mock_data.py.
// Dates are relative to today so the sample never goes stale.

const day = (offset: number) => toISODate(addDays(new Date(), offset));
/** ISO date-time `offset` days from now at hh:mm local time. */
const at = (offset: number, h: number, m: number) => {
  const d = addDays(new Date(), offset);
  d.setHours(h, m, 0, 0);
  return d.toISOString();
};
const tracked = { source: "both", hasTailoredResume: true, needsReview: false } as const;

export const mockApplications: Application[] = [
  { id: "1", company: "Northwind", role: "Software Engineer", status: "interviewing", atsScore: 91, lastUpdateAt: at(0, 9, 12), ...tracked },
  { id: "2", company: "Lumen Labs", role: "Frontend Engineer", status: "offer", atsScore: 88, lastUpdateAt: at(-1, 16, 40), ...tracked },
  { id: "7", company: "Orbital", role: "Platform Engineer", status: "interviewing", atsScore: 82, lastUpdateAt: at(-5, 11, 5), ...tracked },
  { id: "3", company: "Brightpath", role: "Full-Stack Developer", status: "follow_up", atsScore: 84, lastUpdateAt: at(-9, 14, 22), ...tracked },
  { id: "4", company: "Atlas Health", role: "Backend Engineer", status: "applied", atsScore: 79, lastUpdateAt: at(-11, 10, 48), ...tracked },
  { id: "5", company: "Kestrel", role: "Junior ML Engineer", status: "applied", atsScore: 76, lastUpdateAt: at(-14, 8, 30), ...tracked },
  { id: "6", company: "Harbor Pay", role: "Software Engineer II", status: "rejected", atsScore: 72, lastUpdateAt: at(-17, 17, 15), ...tracked },
  { id: "8", company: "Quill", role: "Data Engineer", status: "rejected", atsScore: 68, lastUpdateAt: at(-20, 13, 3), ...tracked },
];

mockApplications.push(
  // Tailored here, not yet confirmed by an email: shown greyed out
  { id: "9", company: "Pinecrest", role: "Software Engineer", status: null, atsScore: 86, lastUpdateAt: null, source: "tailored", hasTailoredResume: true, needsReview: false },
  // Found in the inbox only: no tailored resume to download
  { id: "10", company: "Meridian", role: "Backend Developer", status: "applied", atsScore: null, lastUpdateAt: at(-2, 9, 41), source: "gmail", hasTailoredResume: false, needsReview: false },
);

export const mockStats: ApplicationStats = {
  applied: 18,
  interviewing: 4,
  offers: 1,
  followUpsDue: 3,
};

export const mockDashboard: DashboardData = {
  counts: { applied: 8, interviewing: 4, offer: 1, follow_up: 3, rejected: 2 },
  events: [
    { id: "e1", date: day(-20), kind: "rejected", title: "Rejected · Quill", detail: "Data Engineer" },
    { id: "e2", date: day(-17), kind: "rejected", title: "Rejected · Harbor Pay", detail: "Software Engineer II" },
    { id: "e3", date: day(-14), kind: "applied", title: "Applied · Kestrel", detail: "Junior ML Engineer" },
    { id: "e4", date: day(-11), kind: "applied", title: "Applied · Atlas Health", detail: "Backend Engineer" },
    { id: "e5", date: day(-9), kind: "applied", title: "Applied · Brightpath", detail: "Full-Stack Developer" },
    { id: "e6", date: day(-5), kind: "interviewing", title: "Interview invite · Orbital", detail: "Platform Engineer" },
    { id: "e7", date: day(-1), kind: "offer", title: "Offer · Lumen Labs", detail: "Frontend Engineer" },
    { id: "e8", date: day(0), kind: "follow_up", title: "Follow-up due · Brightpath", detail: "No reply in 9 days" },
    { id: "e9", date: day(0), kind: "interviewing", title: "Interview invite · Northwind", detail: "Software Engineer" },
    { id: "e10", date: day(2), time: "10:00", kind: "interviewing", title: "Interview · Northwind", detail: "Video call", scheduled: true },
    { id: "e11", date: day(3), kind: "follow_up", title: "Follow-up due · Atlas Health", detail: "Backend Engineer" },
    { id: "e12", date: day(4), kind: "offer", title: "Offer deadline · Lumen Labs", detail: "Respond by end of day" },
    { id: "e13", date: day(8), time: "13:30", kind: "interviewing", title: "Interview · Orbital", detail: "Onsite", scheduled: true },
  ],
  reminders: [
    { id: "r1", date: day(2), time: "10:00", kind: "interviewing", company: "Northwind", role: "Software Engineer", message: "Video interview with the engineering team" },
    { id: "r2", date: day(0), kind: "follow_up", company: "Brightpath", role: "Full-Stack Developer", message: "No reply in 9 days. Send a follow-up email." },
    { id: "r3", date: day(3), kind: "follow_up", company: "Atlas Health", role: "Backend Engineer", message: "Check in on your application" },
    { id: "r4", date: day(4), kind: "offer", company: "Lumen Labs", role: "Frontend Engineer", message: "Respond to your offer" },
    { id: "r5", date: day(8), time: "13:30", kind: "interviewing", company: "Orbital", role: "Platform Engineer", message: "Onsite interview" },
  ],
};

export const mockTailorResult: TailorResult = {
  originalScore: 62,
  score: 91,
  matchedKeywords: ["React", "TypeScript", "Node.js", "REST APIs", "PostgreSQL", "CI/CD", "Web apps", "End-to-end ownership"],
  missingKeywords: ["AWS", "Communication"],
  rewrites: [
    {
      id: "r1",
      section: "Experience · Acme Corp",
      before: "Worked on the backend for a web app.",
      after: "Built REST APIs in Node.js and PostgreSQL serving the app’s core booking flow.",
    },
    {
      id: "r2",
      section: "Experience · Acme Corp",
      before: "Helped make deployments faster.",
      after: "Set up a CI/CD pipeline with GitHub Actions, cutting release time from hours to minutes.",
    },
    {
      id: "r3",
      section: "Projects · Portfolio site",
      before: "Made a personal website with React.",
      after: "Developed a responsive portfolio in React and TypeScript with reusable UI components.",
    },
  ],
  companyBrief: {
    summary:
      "[Short summary from the research agent: what the company does, its products, size and stage.]",
    highlights: [
      "[Recent news item]",
      "[Tech stack signals from the posting]",
      "[Talking point for your cover letter]",
    ],
  },
};

export const sampleJobDescription = `We're looking for a Software Engineer to build and scale our booking platform. You'll work across React, TypeScript and Node.js, design REST APIs backed by PostgreSQL, and own features end to end on AWS.

Requirements: 2+ years building web apps, experience with CI/CD, strong communication skills…`;
