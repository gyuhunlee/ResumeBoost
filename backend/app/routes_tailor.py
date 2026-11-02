"""Resume tailoring endpoints.

Flow
  POST /api/tailor/sessions                 start; the agent runs in the background
  GET  /api/tailor/sessions/{id}            poll: live steps, questions, proposed changes
  POST /api/tailor/sessions/{id}/answers    answer the agent's questions; it resumes
  POST /api/tailor/sessions/{id}/finalize   apply the changes the user accepted, render
                                            PDF + DOCX, save to Applications

Why background + polling: a run is several LLM calls (and free-tier rate limits
can add waits), so it can take 20-60s. Polling shows progress and doesn't depend
on a long-lived request. State is saved after every agent step, so if Render
restarts the instance mid-run the session is marked failed instead of hanging.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from . import tracker
from .auth import CurrentUser, get_current_user
from .db import db, eq
from .schemas import (
    FormatIssue,
    TailorAnswers,
    TailorChange,
    TailorFinalize,
    TailorQuestion,
    TailorScore,
    TailorSession,
    TailorStart,
    TailorStep,
)
from .tailor.agent import Answer, Context, TailorState, answer_questions, apply_changes, run, run_without_llm, start_state
from .tailor.bank import from_resumes, from_rows
from .tailor.jd import analyze_job_description
from .tailor.keywords import score_match
from .tailor.llm import get_llm
from .tailor.parse import parse_resume
from .tailor.render import render_docx, render_pdf

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tailor")

STALE_AFTER = timedelta(minutes=6)   # a 'running' session with no progress this long was interrupted
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---- helpers ---------------------------------------------------------------------
def _row(user_id: str, sid: str) -> dict[str, Any]:
    try:
        UUID(sid)
    except ValueError:
        raise HTTPException(404, "Session not found")
    row = db.select_one("tailor_sessions", {"id": eq(sid), "user_id": eq(user_id), "select": "*"})
    if not row:
        raise HTTPException(404, "Session not found")
    return row


def _save(sid: str, user_id: str, **fields: Any) -> dict[str, Any]:
    return db.update("tailor_sessions", {"id": eq(sid), "user_id": eq(user_id)}, fields)[0]


def _persist(sid: str, user_id: str, state: TailorState, status: str) -> None:
    _save(sid, user_id, status=status, state=state.model_dump(mode="json"))


def _score(d: dict[str, Any]) -> TailorScore | None:
    return TailorScore(score=d["score"], matched=d["matched"], partial=d["partial"], missing=d["missing"]) if d else None


def _view(row: dict[str, Any]) -> TailorSession:
    base = dict(id=row["id"], status=row["status"], company=row["company"], role=row["role"], error=row.get("error"),
                application_id=row.get("application_id"), pdf_path=row.get("pdf_path"), docx_path=row.get("docx_path"))
    if not row.get("state"):
        return TailorSession(**base)
    st = TailorState.model_validate(row["state"])
    return TailorSession(
        **base,
        ai_enabled=st.llm_used,
        job_title=st.job.title,
        steps=[TailorStep(tool=s.tool, summary=s.summary, at=s.at) for s in st.steps],
        questions=[TailorQuestion(id=q.id, question=q.question, keyword=q.keyword, answered=q.answer is not None)
                   for q in st.questions],
        baseline=_score(st.baseline),
        projected=_score(st.projected) if row["status"] != "running" else None,
        changes=[TailorChange(**c.model_dump(exclude={"target_id", "payload"})) for c in st.changes],
        format_issues=[FormatIssue(**i) for i in st.format_issues],
        summary=st.summary,
        final_score=st.final_score,
    )


def _context(user_id: str, resume_id: str) -> Context:
    items = db.select("experience_items", {"user_id": eq(user_id), "select": "*"})
    resumes = db.select("resumes", {"user_id": eq(user_id), "select": "id,title,content"})
    return Context(from_rows(items) + from_resumes(resumes, exclude_id=resume_id))


def _fail(sid: str, user_id: str, message: str) -> None:
    try:
        _save(sid, user_id, status="error", error=message)
    except Exception:
        log.exception("could not mark session %s as failed", sid)


# ---- background work ---------------------------------------------------------------
def _run_new(sid: str, user_id: str, resume: dict[str, Any], req: TailorStart) -> None:
    try:
        llm = get_llm()
        original = parse_resume(resume["content"], llm)
        if not any(True for _ in original.bullets()):
            return _fail(sid, user_id, "Couldn't find any resume content. Check the resume text in Settings.")
        job = analyze_job_description(req.job_description, req.role, llm)
        state = start_state(original, job, req.job_description, llm_used=llm is not None)
        _persist(sid, user_id, state, "running")
        if llm is None:
            status = run_without_llm(state)
        else:
            status = run(state, llm, _context(user_id, resume["id"]),
                         on_step=lambda s: _persist(sid, user_id, s, "running"))
        _persist(sid, user_id, state, status)
    except Exception:
        log.exception("tailor session %s failed", sid)
        _fail(sid, user_id, "Something went wrong while tailoring. Try again.")


def _resume(sid: str, user_id: str, state: TailorState, resume_id: str | None) -> None:
    try:
        llm = get_llm()
        if llm is None:
            status = run_without_llm(state)
        else:
            status = run(state, llm, _context(user_id, resume_id or ""),
                         on_step=lambda s: _persist(sid, user_id, s, "running"))
        _persist(sid, user_id, state, status)
    except Exception:
        log.exception("tailor session %s failed on resume", sid)
        _fail(sid, user_id, "Something went wrong while tailoring. Try again.")


# ---- routes ------------------------------------------------------------------------
@router.post("/sessions", response_model=TailorSession, status_code=201)
def start_session(req: TailorStart, background: BackgroundTasks,
                  user: CurrentUser = Depends(get_current_user)) -> TailorSession:
    params = {"user_id": eq(user.id), "select": "id,title,content", "order": "updated_at.desc"}
    if req.resume_id:
        try:
            UUID(req.resume_id)
        except ValueError:
            raise HTTPException(404, "Resume not found")
        params["id"] = eq(req.resume_id)
    resume = db.select_one("resumes", params)
    if not resume:
        raise HTTPException(400, "Upload a resume in Settings first.")
    if len((resume.get("content") or "").split()) < 30:
        raise HTTPException(422, "That resume has almost no text. Edit it in Settings first.")

    row = db.insert("tailor_sessions", {"user_id": user.id, "resume_id": resume["id"], "company": req.company.strip(),
                                        "role": req.role.strip(), "status": "running"})[0]
    background.add_task(_run_new, row["id"], user.id, resume, req)
    return _view(row)


@router.get("/sessions/{sid}", response_model=TailorSession)
def get_session(sid: str, user: CurrentUser = Depends(get_current_user)) -> TailorSession:
    row = _row(user.id, sid)
    if row["status"] == "running":
        updated = datetime.fromisoformat(row["updated_at"])
        if datetime.now(timezone.utc) - updated > STALE_AFTER:
            row = _save(sid, user.id, status="error", error="Tailoring was interrupted (the server restarted). Try again.")
    return _view(row)


@router.post("/sessions/{sid}/answers", response_model=TailorSession)
def post_answers(sid: str, body: TailorAnswers, background: BackgroundTasks,
                 user: CurrentUser = Depends(get_current_user)) -> TailorSession:
    row = _row(user.id, sid)
    if row["status"] != "needs_input":
        raise HTTPException(409, "This session isn't waiting for answers.")
    state = TailorState.model_validate(row["state"])
    answer_questions(state, {a.question_id: Answer(confirmed=a.confirmed, detail=a.detail.strip())
                             for a in body.answers})
    row = _save(sid, user.id, status="running", state=state.model_dump(mode="json"))
    background.add_task(_resume, sid, user.id, state, row.get("resume_id"))
    return _view(row)


@router.post("/sessions/{sid}/finalize", response_model=TailorSession)
def finalize(sid: str, body: TailorFinalize, user: CurrentUser = Depends(get_current_user)) -> TailorSession:
    """Apply only the changes the user accepted (or edited), render, store, save to Applications.
    Can be called again with different decisions; the files are overwritten."""
    row = _row(user.id, sid)
    if row["status"] not in ("review", "finalized"):
        raise HTTPException(409, "Tailoring isn't finished yet.")
    state = TailorState.model_validate(row["state"])
    known = {c.id for c in state.changes}
    decisions = {d.change_id: {"action": d.action, "text": d.text or ""} for d in body.decisions if d.change_id in known}
    doc = apply_changes(state.original, state.changes, decisions)

    final = score_match(doc, state.job)["score"]
    pdf_path, docx_path = f"{user.id}/tailored-{sid}.pdf", f"{user.id}/tailored-{sid}.docx"
    try:
        db.upload_file("resumes", pdf_path, render_pdf(doc), PDF)
        db.upload_file("resumes", docx_path, render_docx(doc), DOCX)
    except Exception:
        log.exception("could not store tailored resume for %s", sid)
        raise HTTPException(500, "Couldn't save the tailored resume. Try again.")

    app_id = tracker.save_tailored(user.id, row["company"], row["role"], state.job_description, final, pdf_path)
    state.final_score = final
    row = _save(sid, user.id, status="finalized", state=state.model_dump(mode="json"), application_id=app_id,
                pdf_path=pdf_path, docx_path=docx_path)
    return _view(row)
