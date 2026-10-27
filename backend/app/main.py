"""Tailored API — FastAPI backend.

Run locally:  uvicorn app.main:app --reload --port 8000
Docs:         http://localhost:8000/docs
"""

import re

from fastapi import Depends, File, HTTPException, UploadFile, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .auth import CurrentUser, get_current_user
from .resume_text import extract_text

from . import mock_data
from .schemas import ApplicationList, DashboardData, TailorRequest, TailorResult
from .config import settings

MAX_BYTES = 5 * 1024 * 1024

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
def list_applications(user: CurrentUser = Depends(get_current_user)) -> ApplicationList:
    return ApplicationList(stats=mock_data.STATS, items=mock_data.applications())


@app.get("/api/dashboard", response_model=DashboardData)
def get_dashboard(user: CurrentUser = Depends(get_current_user)) -> DashboardData:
    # The frontend hides calendar events dated before the user's sign-up day.
    # When the Gmail tracker is built, also only fetch mail after sign-up
    # (Gmail search "after:YYYY/MM/DD") so older emails never reach the database.
    return mock_data.dashboard()

@app.get("/api/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str | None]:
    return {"id": user.id, "email": user.email}


@app.post("/api/resumes/extract")
async def extract_resume(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),  # only signed-in users
) -> dict[str, str]:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 5 MB")
    try:
        text = extract_text(data, file.content_type or "")
    except ValueError as e:
        raise HTTPException(415, str(e))
    if not text:
        raise HTTPException(422, "No text found. Scanned PDFs aren't supported yet.")
    return {"text": text}

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
def tailor(req: TailorRequest, user: CurrentUser = Depends(get_current_user)) -> TailorResult:
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
