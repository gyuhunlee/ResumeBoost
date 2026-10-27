"""Sample data so the frontend works before the database and agent exist.
Replace with Supabase queries and LLM calls as you build each feature.
Dates are relative to today so the sample never goes stale."""

from datetime import date, timedelta

from .schemas import (
    Application,
    ApplicationStats,
    CalendarEvent,
    CompanyBrief,
    DashboardData,
    Reminder,
    Rewrite,
    StatusCounts,
)


def _day(offset: int) -> date:
    return date.today() + timedelta(days=offset)


def applications() -> list[Application]:
    return [
        Application(id="1", company="Northwind", role="Software Engineer", status="interviewing", ats_score=91, last_update_at=_day(0)),
        Application(id="2", company="Lumen Labs", role="Frontend Engineer", status="offer", ats_score=88, last_update_at=_day(-1)),
        Application(id="7", company="Orbital", role="Platform Engineer", status="interviewing", ats_score=82, last_update_at=_day(-5)),
        Application(id="3", company="Brightpath", role="Full-Stack Developer", status="follow_up", ats_score=84, last_update_at=_day(-9)),
        Application(id="4", company="Atlas Health", role="Backend Engineer", status="applied", ats_score=79, last_update_at=_day(-11)),
        Application(id="5", company="Kestrel", role="Junior ML Engineer", status="applied", ats_score=76, last_update_at=_day(-14)),
        Application(id="6", company="Harbor Pay", role="Software Engineer II", status="rejected", ats_score=72, last_update_at=_day(-17)),
        Application(id="8", company="Quill", role="Data Engineer", status="rejected", ats_score=68, last_update_at=_day(-20)),
    ]


STATS = ApplicationStats(applied=18, interviewing=4, offers=1, follow_ups_due=3)


def dashboard() -> DashboardData:
    E = CalendarEvent
    R = Reminder
    return DashboardData(
        counts=StatusCounts(applied=8, interviewing=4, offer=1, follow_up=3, rejected=2),
        events=[
            E(id="e1", date=_day(-20), kind="rejected", title="Rejected · Quill", detail="Data Engineer"),
            E(id="e2", date=_day(-17), kind="rejected", title="Rejected · Harbor Pay", detail="Software Engineer II"),
            E(id="e3", date=_day(-14), kind="applied", title="Applied · Kestrel", detail="Junior ML Engineer"),
            E(id="e4", date=_day(-11), kind="applied", title="Applied · Atlas Health", detail="Backend Engineer"),
            E(id="e5", date=_day(-9), kind="applied", title="Applied · Brightpath", detail="Full-Stack Developer"),
            E(id="e6", date=_day(-5), kind="interviewing", title="Interview invite · Orbital", detail="Platform Engineer"),
            E(id="e7", date=_day(-1), kind="offer", title="Offer · Lumen Labs", detail="Frontend Engineer"),
            E(id="e8", date=_day(0), kind="follow_up", title="Follow-up due · Brightpath", detail="No reply in 9 days"),
            E(id="e9", date=_day(0), kind="interviewing", title="Interview invite · Northwind", detail="Software Engineer"),
            E(id="e10", date=_day(2), time="10:00", kind="interviewing", title="Interview · Northwind", detail="Video call"),
            E(id="e11", date=_day(3), kind="follow_up", title="Follow-up due · Atlas Health", detail="Backend Engineer"),
            E(id="e12", date=_day(4), kind="offer", title="Offer deadline · Lumen Labs", detail="Respond by end of day"),
            E(id="e13", date=_day(8), time="13:30", kind="interviewing", title="Interview · Orbital", detail="Onsite"),
        ],
        reminders=[
            R(id="r1", date=_day(2), time="10:00", kind="interviewing", company="Northwind", role="Software Engineer", message="Video interview with the engineering team"),
            R(id="r2", date=_day(0), kind="follow_up", company="Brightpath", role="Full-Stack Developer", message="No reply in 9 days. Send a follow-up email."),
            R(id="r3", date=_day(3), kind="follow_up", company="Atlas Health", role="Backend Engineer", message="Check in on your application"),
            R(id="r4", date=_day(4), kind="offer", company="Lumen Labs", role="Frontend Engineer", message="Respond to your offer"),
            R(id="r5", date=_day(8), time="13:30", kind="interviewing", company="Orbital", role="Platform Engineer", message="Onsite interview"),
        ],
    )

# Skills the sample resume already shows. In the real app this comes from the
# user's parsed resume stored in the database.
RESUME_SKILLS = {
    "react", "typescript", "node.js", "rest apis", "postgresql", "ci/cd",
    "python", "git", "web apps",
}

# A small vocabulary for the placeholder keyword extractor. The real version
# asks the LLM to extract requirements from the job description.
SKILL_VOCAB = [
    "React", "TypeScript", "JavaScript", "Node.js", "Python", "FastAPI", "Django",
    "REST APIs", "GraphQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "AWS", "GCP",
    "Azure", "Docker", "Kubernetes", "CI/CD", "Git", "Web apps", "Machine learning",
    "Communication", "Testing",
]

REWRITES = [
    Rewrite(id="r1", section="Experience · Acme Corp", before="Worked on the backend for a web app.", after="Built REST APIs in Node.js and PostgreSQL serving the app’s core booking flow."),
    Rewrite(id="r2", section="Experience · Acme Corp", before="Helped make deployments faster.", after="Set up a CI/CD pipeline with GitHub Actions, cutting release time from hours to minutes."),
    Rewrite(id="r3", section="Projects · Portfolio site", before="Made a personal website with React.", after="Developed a responsive portfolio in React and TypeScript with reusable UI components."),
]


def company_brief(company: str) -> CompanyBrief:
    return CompanyBrief(
        summary=f"[Research agent summary of {company}: what it does, its products, size and stage.]",
        highlights=[
            "[Recent news item]",
            "[Tech stack signals from the posting]",
            "[Talking point for your cover letter]",
        ],
    )
