"""Sample data so the frontend works before the database and agent exist.
Replace with Supabase queries and LLM calls as you build each feature."""

from .schemas import Application, ApplicationStats, CompanyBrief, Rewrite

APPLICATIONS = [
    Application(id="1", company="Northwind", role="Software Engineer", status="interviewing", ats_score=91, last_update="Interview invite · Today"),
    Application(id="2", company="Lumen Labs", role="Frontend Engineer", status="offer", ats_score=88, last_update="Offer email · Yesterday"),
    Application(id="3", company="Brightpath", role="Full-Stack Developer", status="follow_up", ats_score=84, last_update="No reply · 9 days"),
    Application(id="4", company="Atlas Health", role="Backend Engineer", status="applied", ats_score=79, last_update="Confirmation · Oct 15"),
    Application(id="5", company="Kestrel", role="Junior ML Engineer", status="applied", ats_score=76, last_update="Confirmation · Oct 12"),
    Application(id="6", company="Harbor Pay", role="Software Engineer II", status="rejected", ats_score=72, last_update="Update · Oct 9"),
]

STATS = ApplicationStats(applied=18, interviewing=4, offers=1, follow_ups_due=3)

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
