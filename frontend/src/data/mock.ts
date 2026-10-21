import type { Application, ApplicationStats, TailorResult } from "../types";

// Sample data used when the backend isn't running, so the UI still renders.
// The backend returns the same shapes from backend/app/mock_data.py.

export const mockApplications: Application[] = [
  { id: "1", company: "Northwind", role: "Software Engineer", status: "interviewing", atsScore: 91, lastUpdate: "Interview invite · Today" },
  { id: "2", company: "Lumen Labs", role: "Frontend Engineer", status: "offer", atsScore: 88, lastUpdate: "Offer email · Yesterday" },
  { id: "3", company: "Brightpath", role: "Full-Stack Developer", status: "follow_up", atsScore: 84, lastUpdate: "No reply · 9 days" },
  { id: "4", company: "Atlas Health", role: "Backend Engineer", status: "applied", atsScore: 79, lastUpdate: "Confirmation · Oct 15" },
  { id: "5", company: "Kestrel", role: "Junior ML Engineer", status: "applied", atsScore: 76, lastUpdate: "Confirmation · Oct 12" },
  { id: "6", company: "Harbor Pay", role: "Software Engineer II", status: "rejected", atsScore: 72, lastUpdate: "Update · Oct 9" },
];

export const mockStats: ApplicationStats = {
  applied: 18,
  interviewing: 4,
  offers: 1,
  followUpsDue: 3,
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
