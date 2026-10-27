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
    status: ApplicationStatus
    ats_score: int = Field(ge=0, le=100)
    last_update_at: dt.date  # day of the latest email for this application; sent as "YYYY-MM-DD"


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
