"""Builds the Applications page and Dashboard from the database."""

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .db import db, eq
from .gmail.matching import find_match, norm_company, norm_role
from .schemas import (
    Application,
    ApplicationDetail,
    ApplicationStats,
    CalendarEvent,
    DashboardData,
    EmailEvent,
    Reminder,
    StatusCounts,
)

FOLLOW_UP_AFTER = timedelta(days=7)  # "applied" with no news for this long → follow up


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def effective_status(row: dict[str, Any], now: datetime) -> str | None:
    """'applied' turns into 'follow_up' once it has been quiet for a week."""
    if row["status"] == "applied":
        last = _dt(row["status_updated_at"])
        if last and now - last >= FOLLOW_UP_AFTER:
            return "follow_up"
    return row["status"]


def _to_app(row: dict[str, Any], now: datetime) -> Application:
    return Application(
        id=row["id"], company=row["company"], role=row["role"],
        status=effective_status(row, now), ats_score=row["ats_score"],
        last_update_at=_dt(row["status_updated_at"]), source=row["source"],
        has_tailored_resume=bool(row["tailored_resume_path"]), needs_review=row["needs_review"],
    )


def _rows(user_id: str) -> list[dict[str, Any]]:
    return db.select("applications", {"user_id": eq(user_id), "select": "*",
                                      "order": "status_updated_at.desc.nullsfirst"})


def list_applications(user_id: str) -> tuple[ApplicationStats, list[Application]]:
    now = datetime.now(timezone.utc)
    items = [_to_app(r, now) for r in _rows(user_id)]
    statuses = [a.status for a in items]
    stats = ApplicationStats(
        applied=sum(s is not None for s in statuses),  # everything actually submitted
        interviewing=statuses.count("interviewing"),
        offers=statuses.count("offer"),
        follow_ups_due=statuses.count("follow_up"),
    )
    return stats, items


def get_application(user_id: str, app_id: str) -> ApplicationDetail | None:
    try:
        UUID(app_id)
    except ValueError:
        return None  # not an id we could have issued (e.g. a sample-data id)
    row = db.select_one("applications", {"id": eq(app_id), "user_id": eq(user_id), "select": "*"})
    if not row:
        return None
    emails = db.select("email_events", {
        "application_id": eq(app_id), "user_id": eq(user_id), "order": "received_at.desc",
        "select": "id,type,subject,sender,received_at,interview_at"})
    base = _to_app(row, datetime.now(timezone.utc))
    return ApplicationDetail(
        **base.model_dump(),
        job_description=row["job_description"], tailored_resume_path=row["tailored_resume_path"],
        applied_at=_dt(row["applied_at"]),
        created_at=_dt(row["created_at"]), updated_at=_dt(row["updated_at"]),
        emails=[EmailEvent(**e) for e in emails],
    )


def save_tailored(user_id: str, company: str, role: str, job_description: str, ats_score: int) -> str:
    """Create (or merge into) the application row for a tailored resume. Returns its id."""
    apps = db.select("applications", {"user_id": eq(user_id), "select": "*"})
    match = find_match(apps, company, role)
    fields = {"job_description": job_description, "ats_score": ats_score}
    if match.application:
        app = match.application
        if app["source"] == "gmail":
            fields["source"] = "both"
        db.update("applications", {"id": eq(app["id"]), "user_id": eq(user_id)}, fields)
        return app["id"]
    row = db.insert("applications", {
        "user_id": user_id, "company": company, "company_norm": norm_company(company),
        "role": role, "role_norm": norm_role(role), "source": "tailored", **fields,
    })[0]
    return row["id"]


# ---- Dashboard -----------------------------------------------------------------
EVENT_TITLE = {"applied": "Applied", "interviewing": "Interview invite",
               "offer": "Offer", "rejected": "Rejected"}


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def dashboard(user_id: str, tz_name: str | None) -> DashboardData:
    tz = _tz(tz_name)
    now = datetime.now(timezone.utc)
    today = now.astimezone(tz).date()
    rows = _rows(user_id)
    by_id = {r["id"]: r for r in rows}
    emails = db.select("email_events", {"user_id": eq(user_id), "order": "received_at.asc",
                                        "select": "id,application_id,type,received_at,interview_at,subject"})

    def local(ts: datetime) -> tuple[date, str]:
        t = ts.astimezone(tz)
        return t.date(), t.strftime("%H:%M")

    counts = {"applied": 0, "interviewing": 0, "offer": 0, "follow_up": 0, "rejected": 0}
    events: list[CalendarEvent] = []
    reminders: list[Reminder] = []

    for r in rows:
        status = effective_status(r, now)
        if status is None:
            continue  # tailored but not submitted: not part of the pipeline yet
        counts[status] += 1
        if r["status"] == "applied" and r["status_updated_at"]:
            due = _dt(r["status_updated_at"]) + FOLLOW_UP_AFTER
            due_day = due.astimezone(tz).date()
            events.append(CalendarEvent(id=f"follow-{r['id']}", date=due_day, kind="follow_up",
                                        title=f"Follow-up due · {r['company']}", detail=r["role"] or "No reply yet"))
            reminders.append(Reminder(
                id=f"follow-{r['id']}-{due_day}", date=max(due_day, today), kind="follow_up",
                company=r["company"], role=r["role"],
                message=f"No reply since {_dt(r['status_updated_at']).astimezone(tz):%b %-d}. Consider a follow-up email."))

    for e in emails:
        app = by_id.get(e["application_id"])
        if not app:
            continue
        d, t = local(_dt(e["received_at"]))
        events.append(CalendarEvent(id=e["id"], date=d, time=t, kind=e["type"],
                                    title=f"{EVENT_TITLE[e['type']]} · {app['company']}",
                                    detail=app["role"] or e["subject"]))
        if e["interview_at"]:
            when = _dt(e["interview_at"])
            d2, t2 = local(when)
            events.append(CalendarEvent(id=f"{e['id']}-iv", date=d2, time=t2, kind="interviewing",
                                        title=f"Interview · {app['company']}", detail=app["role"],
                                        scheduled=True))
            if when >= now:
                reminders.append(Reminder(id=f"iv-{e['id']}", date=d2, time=t2, kind="interviewing",
                                          company=app["company"], role=app["role"],
                                          message="Upcoming interview"))

    return DashboardData(counts=StatusCounts(**counts), events=events, reminders=reminders)
