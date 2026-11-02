"""Tailored API — FastAPI backend.

Run locally:  uvicorn app.main:app --reload --port 8000
Docs:         http://localhost:8000/docs
"""

import logging

from fastapi import Depends, File, HTTPException, Query, UploadFile, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .auth import CurrentUser, get_current_user
from .resume_text import extract_text

from . import tracker
from .db import db, eq
from .routes_gmail import revoke_gmail, router as gmail_router
from .routes_tailor import router as tailor_router
from .schemas import ApplicationDetail, ApplicationList, DashboardData
from .config import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024

app = FastAPI(title="Tailored API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(gmail_router)
app.include_router(tailor_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    # Point a free uptime pinger here if you want to reduce cold starts.
    return {"status": "ok"}


@app.get("/api/applications", response_model=ApplicationList)
def list_applications(user: CurrentUser = Depends(get_current_user)) -> ApplicationList:
    stats, items = tracker.list_applications(user.id)
    return ApplicationList(stats=stats, items=items)


@app.get("/api/applications/{app_id}", response_model=ApplicationDetail)
def get_application(app_id: str, user: CurrentUser = Depends(get_current_user)) -> ApplicationDetail:
    detail = tracker.get_application(user.id, app_id)
    if detail is None:
        raise HTTPException(404, "Application not found")
    return detail


@app.get("/api/dashboard", response_model=DashboardData)
def get_dashboard(
    tz: str | None = Query(default=None, description="IANA time zone, e.g. America/Los_Angeles"),
    user: CurrentUser = Depends(get_current_user),
) -> DashboardData:
    # The Gmail sync only reads mail received after sign-up, and the frontend
    # also hides calendar days before sign-up.
    return tracker.dashboard(user.id, tz)


@app.delete("/api/account", status_code=204)
def delete_account(user: CurrentUser = Depends(get_current_user)) -> None:
    """Permanently deletes the user: Gmail access, stored files, then the login.
    Deleting the auth user cascades to profiles, resumes, applications,
    email_events and gmail_accounts (all reference auth.users ON DELETE CASCADE)."""
    acc = db.select_one("gmail_accounts", {"user_id": eq(user.id)})
    if acc:
        revoke_gmail(acc)  # also tell Google, so the app loses inbox access
    try:
        db.remove_user_files("resumes", user.id)
    except Exception:
        log.exception("could not delete stored files for %s", user.id)
        raise HTTPException(500, "Couldn't delete your files. Nothing was removed; try again.")
    db.delete_auth_user(user.id)

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
