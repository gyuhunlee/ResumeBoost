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


class TailorRequest(CamelModel):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    job_description: str = Field(min_length=20, max_length=20_000)
    # False for previews (the page's first load) so they don't create application rows.
    save: bool = True


class Rewrite(CamelModel):
    id: str
    section: str
    before: str
    after: str


class CompanyBrief(CamelModel):
    summary: str
    highlights: list[str]


class TailorResult(CamelModel):
    original_score: int
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    rewrites: list[Rewrite]
    company_brief: CompanyBrief
    application_id: str | None = None  # the applications row this tailoring was saved to
