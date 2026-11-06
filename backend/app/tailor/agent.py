"""The tailoring agent: an LLM in a tool-calling loop over the tools in this package.

Division of labor
  code   parses, scores, verifies, renders and saves (must be correct, reproducible)
  LLM    decides what to emphasize, how to reword, what to ask (needs judgment)

Every edit is recorded as a Change against the ORIGINAL resume, never applied
in place. The "working" resume is rebuilt from original + changes whenever a
tool needs it, so the user can later accept/reject each change independently.

State is a JSON-serializable TailorState, saved after every step. That lets the
agent pause on ask_user (the HTTP request ends, the user answers minutes later,
a new request resumes the loop) and lets the UI poll a live trace.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .bank import BankItem, search_experience_bank
from .formatting import check_format
from .keywords import canonical, keyword_gap, score_match, term_in
from .llm import LLM, LLMError
from .models import Bullet, Entry, JobAnalysis, ResumeDoc
from .style import ResumeStyle
from .verify import verify_claims

log = logging.getLogger(__name__)

MAX_TURNS = 10        # model calls per run (each is one request against the free-tier RPM limit)
MAX_QUESTIONS = 3     # ask_user questions per session
MAX_CHANGES = 20
MAX_BANK_BULLETS = 4


# ---- State -----------------------------------------------------------------------
class Change(BaseModel):
    id: str
    kind: Literal["rewrite", "add_bullets", "add_entry", "remove", "reorder"]
    target_id: str            # bullet / entry / section id the change applies to
    section: str = ""         # display only
    entry: str = ""           # display only
    before: str = ""
    after: str = ""
    keywords: list[str] = Field(default_factory=list)
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class Answer(BaseModel):
    confirmed: bool | None = None   # yes / no / (None = free-text only)
    detail: str = ""


class Question(BaseModel):
    id: str
    question: str
    keyword: str = ""
    answer: Answer | None = None


class Step(BaseModel):
    tool: str
    summary: str
    at: str


class TailorState(BaseModel):
    original: ResumeDoc
    job: JobAnalysis
    job_description: str = ""
    changes: list[Change] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    contents: list[dict[str, Any]] = Field(default_factory=list)
    pending: list[dict[str, Any]] | None = None   # tool responses waiting on ask_user answers
    steps: list[Step] = Field(default_factory=list)
    turns: int = 0
    baseline: dict[str, Any] = Field(default_factory=dict)
    projected: dict[str, Any] = Field(default_factory=dict)
    format_issues: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    final_score: int | None = None
    llm_used: bool = True
    next_id: int = 1
    style: ResumeStyle = Field(default_factory=ResumeStyle)   # look of the uploaded file
    source_path: str = ""      # the uploaded file in storage (a .docx is edited in place at finalize)
    format_mode: str = ""      # how the last export kept the format: original | matched | template
    template: str = ""         # last template exported with ("" = not exported yet)

    def new_id(self, prefix: str) -> str:
        self.next_id += 1
        return f"{prefix}{self.next_id - 1}"

    def log(self, tool: str, summary: str) -> None:
        self.steps.append(Step(tool=tool, summary=summary, at=datetime.now(timezone.utc).isoformat()))


# ---- Applying changes ----------------------------------------------------------------
_ORDER = {"add_entry": 0, "add_bullets": 1, "rewrite": 2, "remove": 3, "reorder": 4}


def apply_changes(original: ResumeDoc, changes: list[Change],
                  decisions: dict[str, dict[str, Any]] | None = None) -> ResumeDoc:
    """original + accepted changes. decisions=None accepts everything (the agent's working view).
    decisions[change_id] = {"action": "accept" | "reject" | "edit", "text": "..."}"""
    doc = original.model_copy(deep=True)
    for ch in sorted(changes, key=lambda c: _ORDER[c.kind]):
        d = (decisions or {}).get(ch.id, {"action": "accept"} if decisions is None else {"action": "reject"})
        action = d.get("action", "reject")
        if action == "reject":
            continue
        edited = (d.get("text") or "").strip() if action == "edit" else ""

        if ch.kind == "add_entry":
            sec = doc.find_section(ch.target_id)
            if sec:
                entry = Entry.model_validate(ch.payload["entry"])
                if edited:
                    entry.bullets = [Bullet(id=f"{entry.id}b{i}", text=t)
                                     for i, t in enumerate(_lines(edited), 1)]
                pos = ch.payload.get("position")
                sec.entries.insert(pos if isinstance(pos, int) else len(sec.entries), entry)
        elif ch.kind == "add_bullets":
            found = doc.find_entry(ch.target_id)
            if found:
                texts = _lines(edited) if edited else ch.payload["bullets"]
                found[1].bullets += [Bullet(id=f"{ch.target_id}+{ch.id}.{i}", text=t) for i, t in enumerate(texts, 1)]
        elif ch.kind == "rewrite":
            found = doc.find_bullet(ch.target_id)
            if found:
                found[2].text = edited or ch.after
        elif ch.kind == "remove":
            for s in doc.sections:
                s.entries = [e for e in s.entries if e.id != ch.target_id]
                for e in s.entries:
                    e.bullets = [b for b in e.bullets if b.id != ch.target_id]
        elif ch.kind == "reorder":
            _reorder(doc, ch.target_id, ch.payload.get("order", []))
    return doc


def _lines(text: str) -> list[str]:
    return [ln.strip(" •-\t") for ln in text.split("\n") if ln.strip(" •-\t")]


def _reorder(doc: ResumeDoc, container_id: str, order: list[str]) -> None:
    def sort(items: list, key: Callable[[Any], str]) -> list:
        rank = {i: n for n, i in enumerate(order)}
        return sorted(items, key=lambda x: rank.get(key(x), len(order)))  # unknown ids keep relative order at end

    if sec := doc.find_section(container_id):
        sec.entries = sort(sec.entries, lambda e: e.id)
    elif found := doc.find_entry(container_id):
        found[1].bullets = sort(found[1].bullets, lambda b: b.id)


# ---- Tools ---------------------------------------------------------------------------
TOOLS: list[dict[str, Any]] = [
    {"name": "get_resume",
     "description": "Current working resume (original + your changes so far) with section/entry/bullet ids.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "keyword_gap",
     "description": "Which job keywords the working resume has exactly, only as a synonym (partial), or is missing.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "score_match",
     "description": "Deterministic 0-100 ATS match score of the working resume vs the job, with the baseline.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "check_format",
     "description": "Format issues in the working resume: length over one page, long/weak bullets, missing sections.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "search_experience_bank",
     "description": "Search experience the user has that is NOT on this resume (saved items and other resume versions). "
                    "Use before concluding a keyword is missing.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Keywords, e.g. 'Docker, CI/CD'"}}, "required": ["query"]}},
    {"name": "verify_claims",
     "description": "Check a draft line for numbers, skills or names that aren't supported by the user's facts.",
     "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "rewrite_bullet",
     "description": "Replace one bullet's text. Must keep every fact from the original and add none. "
                    "Rejected if it contains unsupported numbers or skills. Rewriting the same bullet again replaces "
                    "your earlier rewrite.",
     "parameters": {"type": "object", "properties": {
         "bullet_id": {"type": "string"},
         "new_text": {"type": "string"},
         "keywords": {"type": "array", "items": {"type": "string"}, "description": "Job keywords this rewrite surfaces"},
         "reason": {"type": "string", "description": "One short sentence for the user"}},
         "required": ["bullet_id", "new_text", "reason"]}},
    {"name": "add_from_bank",
     "description": "Copy experience from the bank into the resume verbatim: into an existing entry (entry_id) as "
                    "extra bullets, or as a new entry in a section (section_id). Rewrite the added bullets "
                    "afterwards if needed.",
     "parameters": {"type": "object", "properties": {
         "item_id": {"type": "string"},
         "section_id": {"type": "string", "description": "Section for a new entry"},
         "entry_id": {"type": "string", "description": "Existing entry to append bullets to (instead of section_id)"},
         "bullet_indexes": {"type": "array", "items": {"type": "integer"},
                            "description": "Which bank bullets to copy (default: the first few)"},
         "reason": {"type": "string"}},
         "required": ["item_id", "reason"]}},
    {"name": "remove_item",
     "description": "Remove a bullet or an entry that is irrelevant to this job, to keep the resume to one page.",
     "parameters": {"type": "object", "properties": {
         "target_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["target_id", "reason"]}},
    {"name": "reorder",
     "description": "Reorder the entries of a section (container_id = section id) or the bullets of an entry "
                    "(container_id = entry id) so the most relevant come first.",
     "parameters": {"type": "object", "properties": {
         "container_id": {"type": "string"},
         "ordered_ids": {"type": "array", "items": {"type": "string"}},
         "reason": {"type": "string"}}, "required": ["container_id", "ordered_ids", "reason"]}},
    {"name": "ask_user",
     "description": f"Ask the user yes/no questions, e.g. whether they have a required skill the resume doesn't show. "
                    f"Pauses until they answer. Max {MAX_QUESTIONS} questions per session, so batch them in one call. "
                    "Only ask when the answer could change the resume.",
     "parameters": {"type": "object", "properties": {
         "questions": {"type": "array", "items": {"type": "object", "properties": {
             "question": {"type": "string"},
             "keyword": {"type": "string", "description": "The job keyword this is about, if any"}},
             "required": ["question"]}}},
         "required": ["questions"]}},
    {"name": "finish",
     "description": "Stop when the resume is tailored. Give a 2-3 sentence summary for the user of what you changed "
                    "and anything they should add themselves.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]

SYSTEM = f"""You tailor a resume to one job posting so it passes ATS keyword screening and reads well to a recruiter.

Hard rules
- Never invent anything: no new numbers, tools, employers, titles, dates or achievements. Only use facts in the
  resume, the experience bank, or what the user confirmed via ask_user. The tools reject unsupported claims.
- Keep the user's voice; edits should be targeted, not total rewrites.
- Prefer the posting's exact keyword spelling when the resume already shows the same thing differently
  ("Postgres" -> "PostgreSQL").
- Keep it to one page: if check_format says it is long, remove or merge the least relevant bullets.

Approach
1. Look at the keyword gap. For missing required keywords, search_experience_bank first. If still missing and the
   user plausibly has it, ask_user (batch all questions in ONE call, max {MAX_QUESTIONS} total).
2. Rewrite the bullets that can surface job keywords (usually 3-8 rewrites). Lead with action verbs, show impact
   that is already stated.
3. Reorder so the most relevant entries/bullets come first; remove clearly irrelevant ones if over one page.
4. Call score_match and check_format, fix what you can, then finish.

Efficiency: call several tools in the same turn whenever they don't depend on each other — each turn is a
rate-limited request. You have at most {MAX_TURNS} turns."""


class Context:
    """What tools need besides the state: the bank and the facts corpus."""

    def __init__(self, bank: list[BankItem]) -> None:
        self.bank = bank
        self.bank_by_id = {b.id: b for b in bank}

    def corpus(self, state: TailorState) -> str:
        parts = [state.original.text(), *(b.text() for b in self.bank)]
        for q in state.questions:
            if q.answer and q.answer.confirmed is not False:
                parts.append(q.answer.detail)
                if q.answer.confirmed and q.keyword:
                    parts.append(q.keyword)
        return "\n".join(parts)


def working(state: TailorState) -> ResumeDoc:
    return apply_changes(state.original, state.changes)


def _where(doc: ResumeDoc, target: str) -> tuple[str, str]:
    if f := doc.find_bullet(target):
        return f[0].title, f[1].heading
    if f := doc.find_entry(target):
        return f[0].title, f[1].heading
    if s := doc.find_section(target):
        return s.title, ""
    return "", ""


def _upsert(state: TailorState, change: Change, same: Callable[[Change], bool]) -> Change:
    for i, c in enumerate(state.changes):
        if same(c):
            change.id = c.id
            state.changes[i] = change
            return change
    if len(state.changes) >= MAX_CHANGES:
        raise ValueError(f"Change limit ({MAX_CHANGES}) reached. Finish now.")
    state.changes.append(change)
    return change


def execute(name: str, args: dict[str, Any], state: TailorState, ctx: Context) -> dict[str, Any]:
    doc = working(state)

    if name == "get_resume":
        return doc.compact()

    if name == "keyword_gap":
        return keyword_gap(doc, state.job)

    if name == "score_match":
        res = score_match(doc, state.job)
        return {**res, "baseline": state.baseline.get("score"), "change": res["score"] - state.baseline.get("score", 0)}

    if name == "check_format":
        issues = check_format(doc)
        return {"issues": issues or "none", "word_count": doc.word_count()}

    if name == "search_experience_bank":
        hits = search_experience_bank(ctx.bank, str(args.get("query", "")))
        state.log(name, f"Searched your experience bank for “{args.get('query', '')}” ({len(hits)} found)")
        return {"results": hits} if hits else {"results": [], "note": "Nothing relevant in the bank."}

    if name == "verify_claims":
        return verify_claims(str(args.get("text", "")), ctx.corpus(state))

    if name == "rewrite_bullet":
        bid, new_text = str(args.get("bullet_id", "")), " ".join(str(args.get("new_text", "")).split())
        others = [c for c in state.changes if not (c.kind == "rewrite" and c.target_id == bid)]
        found = apply_changes(state.original, others).find_bullet(bid)
        if not found:
            return {"ok": False, "error": f"No bullet with id {bid}. Call get_resume for current ids."}
        if not new_text:
            return {"ok": False, "error": "new_text is empty"}
        sec, entry, bullet = found
        check = verify_claims(new_text, ctx.corpus(state), bullet.text)
        if not check["ok"]:
            state.log(name, f"Blocked a rewrite in {sec.title} that added unsupported claims")
            return {"ok": False, "problems": check["problems"],
                    "hint": "Remove these claims, or ask_user if the user might really have them."}
        keywords = [k for k in args.get("keywords") or [] if term_in(canonical(k), new_text) or term_in(k, new_text)]
        ch = _upsert(state, Change(
            id=state.new_id("c"), kind="rewrite", target_id=bid, section=sec.title, entry=entry.heading,
            before=bullet.text, after=new_text, keywords=keywords, reason=str(args.get("reason", "")),
            warnings=check["warnings"]), lambda c: c.kind == "rewrite" and c.target_id == bid)
        state.log(name, f"Rewrote a bullet in {sec.title}{' · ' + entry.heading if entry.heading else ''}")
        return {"ok": True, "change_id": ch.id, "keywords_present": keywords, "warnings": check["warnings"]}

    if name == "add_from_bank":
        item = ctx.bank_by_id.get(str(args.get("item_id", "")))
        if not item:
            return {"ok": False, "error": "Unknown item_id. Use an item_id from search_experience_bank."}
        idx = args.get("bullet_indexes") or list(range(min(MAX_BANK_BULLETS, len(item.bullets))))
        texts = [item.bullets[i] for i in idx if isinstance(i, int) and 0 <= i < len(item.bullets)][:MAX_BANK_BULLETS]
        if not texts:
            return {"ok": False, "error": "That item has no bullets to add."}
        reason = str(args.get("reason", ""))
        if eid := args.get("entry_id"):
            found = doc.find_entry(str(eid))
            if not found:
                return {"ok": False, "error": f"No entry with id {eid}"}
            cid = state.new_id("c")
            _upsert(state, Change(id=cid, kind="add_bullets", target_id=found[1].id, section=found[0].title,
                                  entry=found[1].heading, after="\n".join(texts), reason=reason,
                                  payload={"bullets": texts, "item_id": item.id}), lambda c: False)
            ids = [f"{found[1].id}+{cid}.{i}" for i in range(1, len(texts) + 1)]
            state.log(name, f"Added {len(texts)} bullet(s) from your experience bank to {found[1].heading or found[0].title}")
            return {"ok": True, "change_id": cid, "new_bullet_ids": ids}
        sid = str(args.get("section_id") or "")
        sec = doc.find_section(sid)
        if not sec:
            return {"ok": False, "error": "Give section_id (new entry) or entry_id (append bullets)."}
        cid = state.new_id("c")
        entry_id = f"{sec.id}+{cid}"
        heading = " — ".join(x for x in (item.title, item.organization) if x)
        entry = Entry(id=entry_id, heading=heading, dates=item.dates,
                      bullets=[Bullet(id=f"{entry_id}b{i}", text=t) for i, t in enumerate(texts, 1)])
        _upsert(state, Change(id=cid, kind="add_entry", target_id=sec.id, section=sec.title, entry=heading,
                              after="\n".join(texts), reason=reason,
                              payload={"entry": entry.model_dump(), "item_id": item.id}), lambda c: False)
        state.log(name, f"Added “{heading}” from your experience bank to {sec.title}")
        return {"ok": True, "change_id": cid, "entry_id": entry_id, "bullet_ids": [b.id for b in entry.bullets]}

    if name == "remove_item":
        tid = str(args.get("target_id", ""))
        sec_title, entry_title = _where(doc, tid)
        if doc.find_section(tid) or not sec_title:
            return {"ok": False, "error": "target_id must be a bullet or entry id"}
        found_b = doc.find_bullet(tid)
        before = found_b[2].text if found_b else entry_title
        ch = _upsert(state, Change(id=state.new_id("c"), kind="remove", target_id=tid, section=sec_title,
                                   entry=entry_title, before=before, reason=str(args.get("reason", ""))),
                     lambda c: c.kind == "remove" and c.target_id == tid)
        state.log(name, f"Removed {'a bullet' if found_b else 'an entry'} from {sec_title}")
        return {"ok": True, "change_id": ch.id}

    if name == "reorder":
        cid_ = str(args.get("container_id", ""))
        order = [str(i) for i in args.get("ordered_ids") or []]
        if sec := doc.find_section(cid_):
            children, labels = [e.id for e in sec.entries], {e.id: e.heading for e in sec.entries}
            title, kind = sec.title, "entries"
        elif found := doc.find_entry(cid_):
            children, labels = [b.id for b in found[1].bullets], {b.id: b.text for b in found[1].bullets}
            title, kind = found[1].heading or found[0].title, "bullets"
        else:
            return {"ok": False, "error": f"No section or entry with id {cid_}"}
        unknown = [i for i in order if i not in children]
        if unknown:
            return {"ok": False, "error": f"Not children of {cid_}: {unknown}"}
        new = order + [c for c in children if c not in order]
        if new == children:
            return {"ok": True, "note": "Already in that order."}
        ch = _upsert(state, Change(
            id=state.new_id("c"), kind="reorder", target_id=cid_, section=_where(doc, cid_)[0], entry=title,
            before="\n".join(labels[i][:90] for i in children), after="\n".join(labels[i][:90] for i in new),
            reason=str(args.get("reason", "")), payload={"order": new}),
            lambda c: c.kind == "reorder" and c.target_id == cid_)
        state.log(name, f"Reordered {kind} in {title}")
        return {"ok": True, "change_id": ch.id}

    return {"error": f"Unknown tool {name}"}


# ---- Loop ----------------------------------------------------------------------------
def start_state(original: ResumeDoc, job: JobAnalysis, job_description: str, llm_used: bool) -> TailorState:
    state = TailorState(original=original, job=job, job_description=job_description, llm_used=llm_used)
    state.baseline = score_match(original, job)
    state.projected = state.baseline
    state.format_issues = check_format(original)
    state.log("analyze", f"Read your resume ({sum(1 for _ in original.bullets())} lines) and the posting "
                         f"({len(job.required)} required, {len(job.preferred)} preferred keywords)")
    return state


def _intro(state: TailorState, ctx: Context) -> str:
    return json.dumps({
        "job": state.job.model_dump(),
        "baseline_score": state.baseline,
        "keyword_gap": keyword_gap(state.original, state.job),
        "format_issues": state.format_issues,
        "experience_bank_items": len(ctx.bank),
        "resume": state.original.compact(),
    }, ensure_ascii=False)


def _finalize(state: TailorState) -> None:
    doc = working(state)
    state.projected = score_match(doc, state.job)
    state.format_issues = check_format(doc)


def run(state: TailorState, llm: LLM, ctx: Context,
        on_step: Callable[[TailorState], None] = lambda s: None) -> Literal["needs_input", "review"]:
    """Runs (or resumes) the loop. Returns 'needs_input' when paused on ask_user."""
    if not state.contents:
        state.contents.append({"role": "user", "parts": [{"text": "Tailor this resume.\n" + _intro(state, ctx)}]})

    while state.turns < MAX_TURNS:
        state.turns += 1
        try:
            turn = llm.generate(state.contents, system=SYSTEM, tools=TOOLS)
        except LLMError as e:
            log.warning("agent turn failed: %s", e)
            state.log("error", "The AI model stopped responding (rate limit or outage). Showing the changes made so far.")
            break
        state.contents.append(turn)
        calls = [p["functionCall"] for p in turn.get("parts", []) if "functionCall" in p]
        if not calls:  # plain text answer = done
            text = " ".join(p.get("text", "") for p in turn.get("parts", [])).strip()
            state.summary = state.summary or text[:1000]
            break

        responses: list[dict[str, Any]] = []
        asked: list[str] = []
        finished = False
        for call in calls:
            name, args = call.get("name", ""), call.get("args") or {}
            if name == "ask_user":
                asked = _ask(state, args)
                result: dict[str, Any] = {"__ask__": asked} if asked else {
                    "error": f"Question limit ({MAX_QUESTIONS}) reached. Continue without asking."}
            elif name == "finish":
                state.summary = str(args.get("summary", ""))[:1000]
                finished = True
                result = {"ok": True}
            else:
                try:
                    result = execute(name, args, state, ctx)
                except Exception as e:  # a tool bug shouldn't kill the session; let the model adapt
                    log.exception("tool %s failed", name)
                    result = {"error": str(e)}
            fr: dict[str, Any] = {"name": name, "response": result}
            if call.get("id"):
                fr["id"] = call["id"]
            responses.append({"functionResponse": fr})

        if asked and not finished:
            state.pending = responses
            on_step(state)
            return "needs_input"
        state.contents.append({"role": "user", "parts": _fill_asks(state, responses)})
        on_step(state)
        if finished:
            break
    else:
        state.log("limit", "Reached the step limit; showing the changes made so far.")

    _finalize(state)
    state.log("done", f"Done — match score {state.baseline.get('score')} → {state.projected.get('score')} "
                      "if you accept every change")
    on_step(state)
    return "review"


def _ask(state: TailorState, args: dict[str, Any]) -> list[str]:
    room = MAX_QUESTIONS - len(state.questions)
    ids = []
    for q in (args.get("questions") or [])[:max(room, 0)]:
        text = str(q.get("question", "")).strip() if isinstance(q, dict) else str(q).strip()
        if not text:
            continue
        qid = state.new_id("q")
        state.questions.append(Question(id=qid, question=text[:300],
                                        keyword=str(q.get("keyword", "")) if isinstance(q, dict) else ""))
        ids.append(qid)
    if ids:
        state.log("ask_user", f"Asked you {len(ids)} question(s)")
    return ids


def _fill_asks(state: TailorState, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {q.id: q for q in state.questions}
    out = []
    for part in responses:
        resp = part["functionResponse"]["response"]
        if isinstance(resp, dict) and "__ask__" in resp:
            answers = []
            for qid in resp["__ask__"]:
                q = by_id[qid]
                a = q.answer or Answer()
                answers.append({"question": q.question, "keyword": q.keyword,
                                "answer": {True: "yes", False: "no", None: "no answer"}[a.confirmed],
                                "details": a.detail})
            part = {"functionResponse": {**part["functionResponse"], "response": {"answers": answers}}}
        out.append(part)
    return out


def answer_questions(state: TailorState, answers: dict[str, Answer]) -> None:
    """Record the user's answers; the next run() call continues from here."""
    for q in state.questions:
        if q.id in answers and q.answer is None:
            q.answer = answers[q.id]
    for q in state.questions:  # unanswered = skipped
        q.answer = q.answer or Answer(confirmed=None)
    if state.pending is not None:
        state.contents.append({"role": "user", "parts": _fill_asks(state, state.pending)})
        state.pending = None
    yes = sum(1 for q in state.questions if q.answer and q.answer.confirmed)
    state.log("answers", f"Got your answers ({yes} yes)")


def run_without_llm(state: TailorState) -> Literal["review"]:
    state.llm_used = False
    state.summary = ("Keyword analysis only: AI rewrites are turned off because GEMINI_API_KEY isn't set on the "
                     "server. The score and missing keywords below are still accurate.")
    _finalize(state)
    return "review"
