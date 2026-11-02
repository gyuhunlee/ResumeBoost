"""API models. Field names are snake_case in Python and camelCase in JSON,
matching frontend/src/types.ts."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


ApplicationStatus = Literal["applied", "interviewing", "offer", "follow_up", "rejected"]


class Application(CamelModel):
    id: str
    company: str
    role: str
    # None = tailored here but no email has confirmed it was submitted yet (row shows greyed out)
    status: ApplicationStatus | None
    ats_score: int | None = Field(default=None, ge=0, le=100)  # None when not tailored here
    # Received time of the email that last changed the status (ISO 8601 with offset).
    last_update_at: dt.datetime | None
    source: Literal["tailored", "gmail", "both"]
    has_tailored_resume: bool  # False disables "Download PDF"
    needs_review: bool = False  # an email was matched to this row without certainty


class EmailEvent(CamelModel):
    id: str
    type: Literal["applied", "interviewing", "offer", "rejected"]
    subject: str
    sender: str
    received_at: dt.datetime
    interview_at: dt.datetime | None = None


class ApplicationDetail(Application):
    job_description: str | None
    tailored_resume_path: str | None  # in the private 'resumes' bucket; the browser signs a URL
    applied_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    emails: list[EmailEvent]


class GmailStatus(CamelModel):
    connected: bool
    gmail_address: str | None = None
    last_synced_at: dt.datetime | None = None
    sync_status: Literal["idle", "running", "error"] | None = None
    last_error: str | None = None
    # Set by POST /api/gmail/sync: how many emails changed an application in this sync.
    changed: int | None = None


class ApplicationStats(CamelModel):
    applied: int
    interviewing: int
    offers: int
    follow_ups_due: int


class ApplicationList(CamelModel):
    stats: ApplicationStats
    items: list[Application]


class StatusCounts(BaseModel):
    # Plain BaseModel on purpose: keys are status names ("follow_up"), not camelCase.
    applied: int
    interviewing: int
    offer: int
    follow_up: int
    rejected: int


class CalendarEvent(CamelModel):
    id: str
    date: dt.date
    time: str | None = None  # "HH:MM", 24h, in the user's time zone
    kind: ApplicationStatus
    title: str
    detail: str
    # True only for a scheduled interview (a date/time named in an email). Only these get a calendar dot.
    scheduled: bool = False


class Reminder(CamelModel):
    id: str
    date: dt.date
    time: str | None = None
    kind: Literal["interviewing", "follow_up", "offer"]
    company: str
    role: str
    message: str


class DashboardData(CamelModel):
    counts: StatusCounts
    events: list[CalendarEvent]
    reminders: list[Reminder]


# ---- Resume tailoring agent ---------------------------------------------------------
class TailorStart(CamelModel):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    job_description: str = Field(min_length=50, max_length=20_000)
    resume_id: str | None = None  # default: the most recently updated resume


class TailorStep(CamelModel):
    tool: str
    summary: str
    at: dt.datetime


class TailorQuestion(CamelModel):
    id: str
    question: str
    keyword: str = ""
    answered: bool = False


class TailorAnswer(CamelModel):
    question_id: str
    confirmed: bool | None = None  # None = skipped
    detail: str = Field(default="", max_length=500)


class TailorAnswers(CamelModel):
    answers: list[TailorAnswer] = Field(max_length=10)


class TailorScore(CamelModel):
    score: int
    matched: list[str]
    partial: list[str]   # present only as a synonym, e.g. "Postgres" for "PostgreSQL"
    missing: list[str]


class TailorChange(CamelModel):
    id: str
    kind: Literal["rewrite", "add_bullets", "add_entry", "remove", "reorder"]
    section: str
    entry: str
    before: str
    after: str
    keywords: list[str]
    reason: str
    warnings: list[str]


class FormatIssue(CamelModel):
    severity: Literal["warning", "info"]
    message: str
    target_id: str | None = None


class TailorSession(CamelModel):
    id: str
    status: Literal["running", "needs_input", "review", "finalized", "error"]
    company: str
    role: str
    error: str | None = None
    ai_enabled: bool = True
    job_title: str = ""
    steps: list[TailorStep] = []
    questions: list[TailorQuestion] = []
    baseline: TailorScore | None = None
    projected: TailorScore | None = None   # score if every change is accepted
    changes: list[TailorChange] = []
    format_issues: list[FormatIssue] = []
    summary: str = ""
    final_score: int | None = None
    application_id: str | None = None
    pdf_path: str | None = None    # private 'resumes' bucket; the browser signs a URL
    docx_path: str | None = None


class TailorDecision(CamelModel):
    change_id: str
    action: Literal["accept", "reject", "edit"]
    text: str | None = Field(default=None, max_length=3000)


class TailorFinalize(CamelModel):
    decisions: list[TailorDecision] = Field(max_length=50)
