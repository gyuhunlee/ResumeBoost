"""Gmail connection and sync endpoints.

Sync triggers (no always-on worker needed on Render's free plan):
  - Dashboard/Applications load: the frontend calls POST /api/gmail/sync when
    the last sync is older than 15 minutes
  - "Sync now" button: same endpoint
  - Daily GitHub Actions job: POST /internal/sync-all (covers inactive users)
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse

from .auth import CurrentUser, get_current_user
from .config import settings
from .db import db, eq
from .gmail import client
from .gmail.sync import AlreadyRunning, acquire_lock, run_locked, sync_all, sync_user
from .schemas import GmailStatus

router = APIRouter()


def _account(user_id: str) -> dict | None:
    return db.select_one("gmail_accounts", {"user_id": eq(user_id)})


def _safe_sync(user_id: str, account: dict | None = None) -> None:
    try:
        run_locked(user_id, account) if account else sync_user(user_id)
    except Exception:
        pass  # the error is saved on gmail_accounts.last_error and shown in the UI


@router.get("/api/gmail/connect-url")
def connect_url(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    if not (settings.google_client_id and settings.google_client_secret and settings.token_encryption_key):
        raise HTTPException(503, "Gmail sync isn't configured on the server yet.")
    return {"url": client.consent_url(user.id, user.email)}


@router.get("/api/gmail/callback")
def callback(background: BackgroundTasks, code: str | None = None, state: str | None = None,
             error: str | None = None) -> RedirectResponse:
    """Google redirects the browser here after the consent screen."""
    back = f"{settings.frontend_url.rstrip('/')}/settings"
    if error or not code or not state:
        return RedirectResponse(f"{back}?gmail=cancelled")
    try:
        user_id = client.user_id_from_state(state)
        tokens = client.exchange_code(code)
    except Exception:  # bad/expired state, or Google rejected the code
        return RedirectResponse(f"{back}?gmail=error")

    existing = _account(user_id)
    if existing and existing["gmail_address"].lower() != tokens.email.lower():
        # Different inbox than before: start the cursor over.
        db.delete("gmail_accounts", {"user_id": eq(user_id)})
        existing = None
    row = {"user_id": user_id, "gmail_address": tokens.email,
           "refresh_token_encrypted": client.encrypt(tokens.refresh_token),
           "sync_status": "idle", "last_error": None}
    db.insert("gmail_accounts", row, on_conflict="user_id", upsert=True)

    background.add_task(_safe_sync, user_id)  # first sync starts right away
    return RedirectResponse(f"{back}?gmail=connected")


@router.get("/api/gmail/status", response_model=GmailStatus)
def status(user: CurrentUser = Depends(get_current_user)) -> GmailStatus:
    acc = _account(user.id)
    if not acc:
        return GmailStatus(connected=False)
    return GmailStatus(connected=True, gmail_address=acc["gmail_address"],
                       last_synced_at=acc["last_synced_at"], sync_status=acc["sync_status"],
                       last_error=acc["last_error"])


@router.post("/api/gmail/sync", response_model=GmailStatus, status_code=202)
def sync_now(background: BackgroundTasks, user: CurrentUser = Depends(get_current_user)) -> GmailStatus:
    """Starts a sync in the background; the frontend polls /api/gmail/status until it's idle."""
    acc = _account(user.id)
    if not acc:
        raise HTTPException(409, "Connect Gmail first.")
    try:
        # Take the lock now, so the very next status poll already says "running".
        locked = acquire_lock(user.id)
        background.add_task(_safe_sync, user.id, locked)
    except AlreadyRunning:
        pass  # a sync is in progress (another tab, or the daily job); just report it
    return GmailStatus(connected=True, gmail_address=acc["gmail_address"],
                       last_synced_at=acc["last_synced_at"], sync_status="running")


@router.delete("/api/gmail", status_code=204)
def disconnect(user: CurrentUser = Depends(get_current_user)) -> None:
    """Revokes access. Applications already found stay on the account."""
    acc = _account(user.id)
    if acc:
        revoke_gmail(acc)
        db.delete("gmail_accounts", {"user_id": eq(user.id)})


def revoke_gmail(acc: dict) -> None:
    try:
        client.revoke(client.decrypt(acc["refresh_token_encrypted"]))
    except Exception:
        pass  # undecryptable token (key rotated): nothing to revoke


@router.post("/internal/sync-all")
def internal_sync_all(x_cron_secret: str = Header(default="")) -> dict:
    if not settings.cron_secret or not secrets.compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(403, "Forbidden")
    started = datetime.now(timezone.utc).isoformat()
    return {"started_at": started, **sync_all()}
