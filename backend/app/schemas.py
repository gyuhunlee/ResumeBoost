"""API models. Field names are snake_case in Python and camelCase in JSON,
matching frontend/src/types.ts."""

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
    last_update: str


class ApplicationStats(CamelModel):
    applied: int
    interviewing: int
    offers: int
    follow_ups_due: int


class ApplicationList(CamelModel):
    stats: ApplicationStats
    items: list[Application]


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
