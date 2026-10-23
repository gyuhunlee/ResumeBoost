import { Link } from "react-router";
import Logo from "../components/Logo";
import {
  ArrowRightIcon,
  ClockIcon,
  LogInIcon,
  MailIcon,
  SearchIcon,
  SparkleIcon,
} from "../components/Icons";
import { Card, Chip, btnPrimary, btnSecondary } from "../components/ui";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthProvider";

const STEPS = [
  {
    title: "Upload your resume",
    body: "Drop in a PDF or DOCX once. It's parsed into sections you can edit anytime.",
  },
  {
    title: "Paste the job description",
    body: "The agent extracts required skills, scores your match, and researches the company.",
  },
  {
    title: "Review and apply",
    body: "Accept the rewrites you like, export an ATS-safe PDF, and it's saved to your tracker.",
  },
];

const FEATURES: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: "Agentic tailoring",
    body: "Rewrites bullets around the role's keywords without inventing experience.",
    icon: <SparkleIcon size={24} />,
  },
  {
    title: "Gmail application tracker",
    body: "Reads confirmation and interview emails to update each application's status.",
    icon: <MailIcon size={24} />,
  },
  {
    title: "Company research",
    body: "A short brief on the company, its products and recent news before you apply.",
    icon: <SearchIcon size={24} />,
  },
  {
    title: "Follow-up reminders",
    body: "Nudges you when an application goes quiet and drafts a polite follow-up.",
    icon: <ClockIcon size={24} />,
  },
];

export default function Landing() {
  const { session, signInWithGoogle } = useAuth();

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-slate-200">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-4">
          <Logo />
          <nav aria-label="Main" className="flex flex-wrap items-center gap-7 text-[15px]">
            <a href="#how" className="text-slate-600 no-underline hover:text-slate-900">
              How it works
            </a>
            <a
              href="https://github.com/gyuhunlee/resumeboost"
              className="text-slate-600 no-underline hover:text-slate-900"
            >
              GitHub
            </a>
            <Link to="/dashboard" className={`${btnSecondary} text-[15px]`}>
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-16 px-6 pt-20 pb-20">
        <div className="flex min-w-0 flex-[1_1_460px] flex-col gap-6">
          <span className="self-start rounded-full bg-blue-50 px-3 py-1.5 text-[13px] font-semibold text-blue-700">
            AI resume tailoring
          </span>
          <h1 className="m-0 text-4xl leading-[1.08] font-bold tracking-tight md:text-[52px]">
            Tailor your resume to every job in minutes.
          </h1>
          <p className="m-0 max-w-[520px] text-[19px] leading-relaxed text-slate-600">
            Paste a job description. An AI agent rewrites your resume for ATS
            keywords, researches the company, and tracks every application
            straight from your inbox.
          </p>
          <div className="flex flex-wrap gap-3">
            {session ? (
              <Link to="/dashboard" className={`${btnPrimary} min-h-12 text-base`}>Go to dashboard</Link>
            ) : (
              <button type="button" onClick={signInWithGoogle} className={`${btnPrimary} min-h-12 cursor-pointer text-base`}>
                <LogInIcon size={18} />
                Continue with Google
              </button>
            )}
            <a href="#how" className={`${btnSecondary} min-h-12 text-base`}>
              See how it works
            </a>
          </div>
          <p className="m-0 text-sm text-slate-500">
            Free to use · Your resume is never shared
          </p>
        </div>

        <HeroPreview />
      </section>

      {/* How it works */}
      <section id="how" className="border-y border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-10 px-6 py-20">
          <div className="flex max-w-[640px] flex-col gap-2.5">
            <h2 className="m-0 text-[34px] font-bold tracking-tight">How it works</h2>
            <p className="m-0 text-[17px] leading-relaxed text-slate-600">
              Three steps from job posting to a resume that gets past the filter.
            </p>
          </div>
          <ol className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-6 p-0">
            {STEPS.map((step, i) => (
              <li key={step.title}>
                <Card className="flex h-full flex-col gap-3 p-7">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 font-bold text-blue-700">
                    {i + 1}
                  </span>
                  <h3 className="m-0 text-[19px] font-semibold">{step.title}</h3>
                  <p className="m-0 text-[15px] leading-relaxed text-slate-600">
                    {step.body}
                  </p>
                </Card>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto flex max-w-[1200px] flex-col gap-10 px-6 py-20">
        <h2 className="m-0 text-[34px] font-bold tracking-tight">
          Everything for the job hunt, in one place
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-8">
          {FEATURES.map((f) => (
            <div key={f.title} className="flex flex-col gap-2.5">
              <span className="text-blue-700">{f.icon}</span>
              <h3 className="m-0 text-[17px] font-semibold">{f.title}</h3>
              <p className="m-0 text-[15px] leading-relaxed text-slate-600">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200">
        <div className="mx-auto flex max-w-[1200px] flex-wrap justify-between gap-4 px-6 py-7 text-sm text-slate-500">
          <span>Built by Gyuhun Lee</span>
          <div className="flex gap-5">
            <a href="https://github.com/gyuhunlee/resumeboost" className="text-slate-600">
              GitHub
            </a>
            <a href="#" className="text-slate-600">
              Privacy
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function HeroPreview() {
  return (
    <div
      className="flex min-w-0 flex-[1_1_440px] flex-col gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-6 shadow-[0_12px_32px_rgba(15,23,42,0.06)]"
      aria-label="Example of a tailored resume result"
      role="figure"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[13px] text-slate-500">Example match</div>
          <div className="font-semibold">Software Engineer · Northwind</div>
        </div>
        <span className="rounded-full bg-green-50 px-2.5 py-1 text-xs font-semibold text-green-700">
          Ready to apply
        </span>
      </div>

      <Card className="flex flex-wrap items-center gap-6 p-5">
        <div>
          <div className="text-[13px] text-slate-500">ATS match score</div>
          <div className="flex items-baseline gap-2.5">
            <span className="text-xl text-slate-400 line-through">62</span>
            <ArrowRightIcon size={16} className="text-slate-500" />
            <span className="text-[40px] font-bold">91</span>
          </div>
        </div>
        <div className="h-2 min-w-40 flex-1 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full w-[91%] rounded-full bg-blue-700" />
        </div>
      </Card>

      <Card className="flex flex-col gap-3 p-5">
        <div className="text-[13px] font-semibold text-slate-600">Keywords</div>
        <div className="flex flex-wrap gap-2">
          {["React", "TypeScript", "REST APIs", "CI/CD"].map((k) => (
            <Chip key={k} tone="match">{k}</Chip>
          ))}
          {["PostgreSQL", "AWS"].map((k) => (
            <Chip key={k} tone="missing">+ {k}</Chip>
          ))}
        </div>
      </Card>

      <Card className="flex flex-col gap-2 p-5">
        <div className="text-[13px] font-semibold text-slate-600">Suggested rewrite</div>
        <div className="text-sm leading-normal text-slate-400 line-through">
          Worked on the backend for a web app.
        </div>
        <div className="text-sm leading-normal">
          Built REST APIs in Node.js and PostgreSQL serving the app's core booking flow.
        </div>
      </Card>
    </div>
  );
}
