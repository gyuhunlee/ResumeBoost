"""Tailored API — FastAPI backend.

Run locally:  uvicorn app.main:app --reload --port 8000
Docs:         http://localhost:8000/docs
"""

import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import mock_data
from .schemas import ApplicationList, TailorRequest, TailorResult


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    cors_origins: str = "http://localhost:5173"


settings = Settings()

app = FastAPI(title="Tailored API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    # Point a free uptime pinger here if you want to reduce cold starts.
    return {"status": "ok"}


@app.get("/api/applications", response_model=ApplicationList)
def list_applications() -> ApplicationList:
    # TODO: query the signed-in user's rows from Supabase; Gmail sync updates them.
    return ApplicationList(stats=mock_data.STATS, items=mock_data.APPLICATIONS)


def extract_keywords(job_description: str) -> list[str]:
    """Placeholder extractor: finds known skills in the posting.
    TODO: replace with an LLM call that returns structured requirements."""
    text = job_description.lower()
    found = []
    for skill in mock_data.SKILL_VOCAB:
        # Match "REST API" as well as "REST APIs", and whole words only.
        pattern = r"(?<![a-z])" + re.escape(skill.lower()).rstrip("s") + r"s?(?![a-z])"
        if re.search(pattern, text):
            found.append(skill)
    return found


@app.post("/api/tailor", response_model=TailorResult)
def tailor(req: TailorRequest) -> TailorResult:
    keywords = extract_keywords(req.job_description)
    matched = [k for k in keywords if k.lower() in mock_data.RESUME_SKILLS]
    missing = [k for k in keywords if k.lower() not in mock_data.RESUME_SKILLS]

    total = max(len(keywords), 1)
    score = round(100 * len(matched) / total)
    # Pretend the original resume covered ~2/3 of what the tailored one does.
    original = round(score * 0.68)

    # TODO: agent step — ask the LLM to rewrite bullets using only facts from
    # the resume, then re-score. Never add skills the user doesn't have.
    return TailorResult(
        original_score=original,
        score=score,
        matched_keywords=matched,
        missing_keywords=missing,
        rewrites=mock_data.REWRITES,
        company_brief=mock_data.company_brief(req.company),
    )
