"""Reads new Gmail messages and turns them into application rows.

    fetch new IDs → prefilter (free) → classify (LLM) → match → upsert

First sync: Gmail search for likely emails received since the user signed up.
Later syncs: Gmail's history API returns only messages added after the stored
historyId, so each sync picks up exactly where the last one stopped.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import db, eq
from . import client
from .classify import BACKFILL_QUERY, classify, prefilter
from .matching import find_match, norm_company, norm_role

log = logging.getLogger(__name__)

MAX_BACKFILL = 300        # messages listed on the first sync
MAX_PER_SYNC = 500        # messages looked at on later syncs
MIN_CONFIDENCE = 0.6
LOCK_TIMEOUT = timedelta(minutes=10)  # a crashed sync releases its lock after this


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class AlreadyRunning(Exception):
    pass


def acquire_lock(user_id: str) -> dict[str, Any]:
    """Atomically flip sync_status to 'running'. Raises if another sync holds it."""
    stale = iso(now() - LOCK_TIMEOUT)
    rows = db.update(
        "gmail_accounts",
        {"user_id": eq(user_id), "or": f"(sync_status.neq.running,sync_started_at.lt.{stale})"},
        {"sync_status": "running", "sync_started_at": iso(now()), "last_error": None},
    )
    if not rows:
        raise AlreadyRunning()
    return rows[0]


def sync_user(user_id: str) -> int:
    """Run one sync. Returns how many emails changed an application."""
    try:
        account = acquire_lock(user_id)
    except AlreadyRunning:
        log.info("sync already running for %s", user_id)
        return 0
    return run_locked(user_id, account)


def run_locked(user_id: str, account: dict[str, Any]) -> int:
    """The sync itself, for a caller that already holds the lock."""
    try:
        changed = _sync(user_id, account)
        db.update("gmail_accounts", {"user_id": eq(user_id)},
                  {"sync_status": "idle", "last_synced_at": iso(now())})
        return changed
    except client.GmailAuthError as e:
        db.update("gmail_accounts", {"user_id": eq(user_id)},
                  {"sync_status": "error", "last_error": f"Reconnect Gmail: {e}"})
        raise
    except Exception as e:
        log.exception("sync failed for %s", user_id)
        db.update("gmail_accounts", {"user_id": eq(user_id)},
                  {"sync_status": "error", "last_error": str(e)[:500]})
        raise


def _sync(user_id: str, account: dict[str, Any]) -> int:
    token = client.refresh_access_token(client.decrypt(account["refresh_token_encrypted"]))
    gmail = client.Gmail(token)

    # Read the cursor BEFORE listing, so mail that arrives mid-sync is caught next time.
    new_history_id = gmail.current_history_id()

    if account.get("history_id"):
        try:
            ids = gmail.added_since(account["history_id"], MAX_PER_SYNC)
        except client.HistoryExpired:
            # historyIds are only kept for about a week; fall back to a date search.
            since = datetime.fromisoformat(account["last_synced_at"]) - timedelta(days=1)
            ids = gmail.search(f"after:{int(since.timestamp())} {BACKFILL_QUERY}", MAX_PER_SYNC)
    else:
        ids = gmail.search(f"after:{int(_signup_time(user_id).timestamp())} {BACKFILL_QUERY}", MAX_BACKFILL)

    changed = _process(user_id, gmail, ids)
    db.update("gmail_accounts", {"user_id": eq(user_id)}, {"history_id": new_history_id})
    return changed


def _signup_time(user_id: str) -> datetime:
    # Only mail from after sign-up is read, matching the dashboard calendar rule.
    profile = db.select_one("profiles", {"id": eq(user_id), "select": "created_at"})
    return datetime.fromisoformat(profile["created_at"]) if profile else now() - timedelta(days=30)


def _process(user_id: str, gmail: client.Gmail, ids: list[str]) -> int:
    if not ids:
        return 0
    seen: set[str] = set()
    for i in range(0, len(ids), 100):  # chunked to keep the URL short
        seen |= {r["gmail_message_id"] for r in db.select(
            "email_events", {"user_id": eq(user_id), "select": "gmail_message_id",
                             "gmail_message_id": f"in.({','.join(ids[i:i + 100])})"})}

    candidates = []
    for mid in ids:
        if mid in seen:
            continue
        meta = gmail.metadata(mid)
        if prefilter(meta.sender, meta.subject, meta.labels):
            candidates.append(meta)

    # Oldest first, so a later rejection lands after the earlier "we received your application".
    candidates.sort(key=lambda m: m.internal_date_ms)

    apps = db.select("applications", {"user_id": eq(user_id), "select": "*"})
    changed = 0
    for meta in candidates:
        received = datetime.fromtimestamp(meta.internal_date_ms / 1000, timezone.utc)
        body = gmail.body_text(meta.id)
        c = classify(meta.sender, meta.subject, body, received)
        if not c.is_job_related or c.type == "other" or c.confidence < MIN_CONFIDENCE or not c.company:
            continue
        app = _apply(user_id, apps, meta, c, received)
        if app:
            changed += 1
    return changed


# Where an email may move an application. An "applied" confirmation that arrives
# late never overrides an interview, offer or rejection.
RANK = {None: -1, "applied": 0, "interviewing": 1, "offer": 2, "rejected": 2}


def _apply(user_id: str, apps: list[dict[str, Any]], meta: client.Message, c, received: datetime):
    match = find_match(apps, c.company, c.role)
    app = match.application

    if app is None:
        rows = db.insert("applications", {
            "user_id": user_id,
            "company": c.company, "company_norm": norm_company(c.company),
            "role": c.role, "role_norm": norm_role(c.role),
            "status": c.type, "source": "gmail",
            "applied_at": iso(received), "status_updated_at": iso(received),
        })
        app = rows[0]
        apps.append(app)
    else:
        changes: dict[str, Any] = {}
        if app["source"] == "tailored":
            changes["source"] = "both"
        if not app["role"] and c.role:
            changes |= {"role": c.role, "role_norm": norm_role(c.role)}
        if not app.get("applied_at"):
            changes["applied_at"] = iso(received)
        if match.needs_review:
            changes["needs_review"] = True

        last = datetime.fromisoformat(app["status_updated_at"]) if app.get("status_updated_at") else None
        newer = last is None or received >= last
        if app["status"] is None or (newer and (c.type != "applied" or RANK[app["status"]] <= 0)):
            changes |= {"status": c.type, "status_updated_at": iso(received)}

        if changes:
            app.update(db.update("applications", {"id": eq(app["id"]), "user_id": eq(user_id)}, changes)[0])

    db.insert("email_events", {
        "user_id": user_id, "application_id": app["id"],
        "gmail_message_id": meta.id, "thread_id": meta.thread_id,
        "type": c.type, "subject": meta.subject[:300], "sender": meta.sender[:200],
        "received_at": iso(received),
        "interview_at": iso(c.interview_at) if c.interview_at else None,
        "confidence": c.confidence,
    }, on_conflict="user_id,gmail_message_id", ignore_duplicates=True)
    return app


def sync_all() -> dict[str, int]:
    """Daily job: sync every connected account. Errors on one user don't stop the rest."""
    ok = failed = 0
    for row in db.select("gmail_accounts", {"select": "user_id"}):
        try:
            sync_user(row["user_id"])
            ok += 1
        except Exception:
            failed += 1
    return {"synced": ok, "failed": failed}
