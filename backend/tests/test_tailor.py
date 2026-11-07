"""Tests for the tailoring tools and agent loop. No network: the LLM is scripted.

Run:  cd backend && python -m pytest -q
"""

from app.tailor.agent import Answer, Context, answer_questions, apply_changes, execute, run, start_state
from app.tailor.bank import BankItem, from_resumes, search_experience_bank
from app.tailor.formatting import check_format
from app.tailor.jd import analyze_rules
from app.tailor.keywords import keyword_gap, score_match, term_in
from app.tailor.models import JobAnalysis
from app.tailor.parse import parse_resume, parse_rules
from app.tailor.render import render_docx, render_pdf
from app.tailor.verify import verify_claims

RESUME = """Gyuhun Lee
gyuhun@example.com | (530) 555-0101 | linkedin.com/in/gyuhun
SUMMARY
Developer who builds web apps with React and Python.
EXPERIENCE
Software Engineer Intern — Acme Corp Jun 2024 – Sep 2024
Davis, CA
• Worked on the backend for a booking web app using Postgres and FastAPI.
• Helped make deployments faster with GitHub Actions, cutting release time by 40%.
• Wrote unit tests for the payments service
  and fixed flaky tests.
Barista — Blue Cup Coffee 2022 – 2024
• Served 200+ customers per shift in a fast-paced environment.
PROJECTS
Resumeboost
• Built a resume tracker with React, TypeScript and Supabase.
EDUCATION
University of California, Davis 2020 – 2024
B.S. Computer Science
SKILLS
Languages: Python, TypeScript, JavaScript, SQL
Tools: Git, Postgres, React, FastAPI
"""

JD = """Software Engineer (Backend)
We need someone with Python, FastAPI, PostgreSQL, REST APIs and Docker.
Experience with CI/CD and unit testing.
Nice to have
Kubernetes, AWS, GraphQL
"""


def job() -> JobAnalysis:
    return JobAnalysis(title="Software Engineer", required=["Python", "FastAPI", "PostgreSQL", "REST APIs", "Docker",
                                                           "CI/CD", "Unit testing"],
                       preferred=["Kubernetes", "AWS", "GraphQL"])


# ---- parse ---------------------------------------------------------------------------
def test_parse_rules_structure():
    doc = parse_rules(RESUME)
    assert doc.name == "Gyuhun Lee"
    assert "gyuhun@example.com" in doc.contact
    kinds = [s.kind for s in doc.sections]
    assert kinds == ["summary", "experience", "projects", "education", "skills"]
    exp = doc.section_of_kind("experience")
    acme, cafe = exp.entries
    assert acme.heading == "Software Engineer Intern — Acme Corp"
    assert acme.dates == "Jun 2024 – Sep 2024"
    assert acme.subheading == "Davis, CA"
    assert len(acme.bullets) == 3
    assert acme.bullets[2].text.endswith("and fixed flaky tests.")  # wrapped line joined
    assert acme.bullets[0].id == "s2e1b1"
    assert cafe.dates == "2022 – 2024"


class FakeLLM:
    def __init__(self, json_reply=None, turns=None):
        self.json_reply, self.turns, self.calls = json_reply, list(turns or []), []

    def generate_json(self, prompt, *, temperature=0):
        return self.json_reply

    def generate(self, contents, *, system, tools, temperature=0.2):
        self.calls.append(contents[-1])
        return self.turns.pop(0)


def test_llm_parse_rejected_when_it_rewords():
    reworded = {"name": "Gyuhun Lee", "contact": [], "sections": [{"title": "Experience", "kind": "experience",
                "entries": [{"heading": "Acme", "bullets": ["Architected a world-class booking platform."]}]}]}
    doc = parse_resume(RESUME, FakeLLM(json_reply=reworded))
    assert len(doc.sections) == 5  # fell back to rules


def test_llm_parse_used_when_faithful():
    faithful = {"name": "Gyuhun Lee", "contact": ["gyuhun@example.com"], "sections": [{"title": "Experience",
                "kind": "experience", "entries": [{"heading": "Barista — Blue Cup Coffee", "dates": "2022 – 2024",
                "bullets": ["Served 200+ customers per shift in a fast-paced environment."]}]}]}
    doc = parse_resume(RESUME, FakeLLM(json_reply=faithful))
    assert len(doc.sections) == 1 and doc.sections[0].entries[0].bullets[0].id == "s1e1b1"


# ---- keywords / score ---------------------------------------------------------------
def test_keyword_gap_levels():
    gap = keyword_gap(parse_rules(RESUME), job())
    exact = {h["keyword"] for h in gap["required"]["exact"]}
    partial = {h["keyword"]: h["found_as"] for h in gap["required"]["partial"]}
    missing = {h["keyword"] for h in gap["required"]["missing"]}
    assert {"Python", "FastAPI"} <= exact
    assert partial.get("PostgreSQL") == "postgres"
    assert "Docker" in missing and "REST APIs" in missing
    assert "Unit testing" in partial  # "unit tests" is an equivalent spelling


def test_term_matching_edge_cases():
    assert term_in("REST APIs", "built a REST API")
    assert term_in("Node.js", "using node.js daily")
    assert term_in("CI/CD", "set up CI/CD")
    assert not term_in("Go", "go to market")      # case-sensitive everyday word
    assert term_in("Go", "services in Go and Python")
    assert not term_in("Java", "JavaScript apps")


def test_score_improves_with_exact_terms():
    doc = parse_rules(RESUME)
    before = score_match(doc, job())["score"]
    doc.sections[1].entries[0].bullets[0].text = "Built REST APIs in FastAPI and PostgreSQL for a booking web app."
    after = score_match(doc, job())["score"]
    assert after > before
    assert 0 <= before <= 100


def test_jd_rules_fallback_splits_preferred():
    a = analyze_rules(JD, "Software Engineer")
    assert "Python" in a.required and "Docker" in a.required
    assert "Kubernetes" in a.preferred and "Kubernetes" not in a.required


# ---- verify -------------------------------------------------------------------------
def test_verify_blocks_invented_numbers_and_skills():
    corpus = parse_rules(RESUME).text()
    r = verify_claims("Built REST APIs with Docker, cutting latency by 35%.", corpus)
    assert not r["ok"]
    joined = " ".join(r["problems"])
    assert "Docker" in joined and "35%" in joined


def test_verify_allows_supported_rewrite_and_synonyms():
    corpus = parse_rules(RESUME).text()
    r = verify_claims("Automated deployments with GitHub Actions CI/CD, cutting release time by 40%.", corpus)
    # CI/CD isn't literally in the resume -> blocked; GitHub Actions and 40% are fine
    assert any("CI/CD" in p for p in r["problems"]) and not any("40" in p for p in r["problems"])
    r2 = verify_claims("Built booking APIs in FastAPI and PostgreSQL.", corpus)  # Postgres == PostgreSQL
    assert r2["ok"], r2


def test_verify_warns_on_unknown_names():
    r = verify_claims("Shipped the booking app used by Netflix.", parse_rules(RESUME).text())
    assert r["ok"] and any("Netflix" in w for w in r["warnings"])


# ---- format / bank / render ---------------------------------------------------------
def test_check_format_flags_weak_starts():
    issues = check_format(parse_rules(RESUME))
    weak = [i for i in issues if "weak phrase" in i["message"]]
    assert {i["target_id"] for i in weak} == {"s2e1b1", "s2e1b2"}


def test_bank_search_and_other_resumes():
    bank = [BankItem(id="bank:1", title="Capstone", bullets=["Containerized the API with Docker."], skills=["Docker"])]
    bank += from_resumes([{"id": "r2", "title": "Old", "content": "EXPERIENCE\nTA — UC Davis\n• Taught SQL labs."}], "r1")
    assert search_experience_bank(bank, "Docker")[0]["item_id"] == "bank:1"
    assert any(i.id.startswith("resume:r2") for i in bank)


def test_render_pdf_and_docx():
    doc = parse_rules(RESUME)
    pdf = render_pdf(doc)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1500
    docx = render_docx(doc)
    assert docx[:2] == b"PK"


# ---- agent --------------------------------------------------------------------------
def call(name, **args):
    return {"functionCall": {"name": name, "args": args}}


def model(*parts):
    return {"role": "model", "parts": list(parts)}


def test_agent_loop_with_ask_user_pause_and_resume():
    original = parse_rules(RESUME)
    bank = [BankItem(id="bank:1", title="Capstone", bullets=["Containerized the API with Docker."], skills=["Docker"])]
    ctx = Context(bank)
    state = start_state(original, job(), JD, llm_used=True)

    llm = FakeLLM(turns=[
        # turn 1: parallel calls incl. an invented claim (blocked) and a question (pauses)
        model(call("keyword_gap"),
              call("rewrite_bullet", bullet_id="s2e1b1", new_text="Built REST APIs with Kubernetes for 1M users.",
                   reason="x"),
              call("ask_user", questions=[{"question": "Have you built REST APIs?", "keyword": "REST APIs"}])),
        # turn 2 (after answers): good rewrite + bank add + reorder + remove
        model(call("rewrite_bullet", bullet_id="s2e1b1",
                   new_text="Built REST APIs for a booking web app using FastAPI and PostgreSQL.",
                   keywords=["REST APIs", "FastAPI", "PostgreSQL", "Docker"], reason="Surfaces backend keywords"),
              call("add_from_bank", item_id="bank:1", section_id="s3", reason="Shows Docker"),
              call("reorder", container_id="s2e1", ordered_ids=["s2e1b2", "s2e1b1"], reason="CI/CD first"),
              call("remove_item", target_id="s2e2", reason="Not relevant")),
        model(call("score_match"), call("check_format")),
        model(call("finish", summary="Rewrote backend bullets and added your Docker capstone.")),
    ])

    status = run(state, llm, ctx)
    assert status == "needs_input"
    assert [q.question for q in state.questions] == ["Have you built REST APIs?"]
    assert state.changes == []  # the invented rewrite was blocked
    assert state.pending is not None

    answer_questions(state, {state.questions[0].id: Answer(confirmed=True, detail="Yes, Flask REST APIs at Acme")})
    # the ask_user response the model receives on resume carries the answer
    ask_resp = [p for p in state.contents[-1]["parts"] if p["functionResponse"]["name"] == "ask_user"][0]
    assert ask_resp["functionResponse"]["response"]["answers"][0]["answer"] == "yes"

    status = run(state, llm, ctx)
    assert status == "review"
    kinds = sorted(c.kind for c in state.changes)
    assert kinds == ["add_entry", "remove", "reorder", "rewrite"]
    rw = next(c for c in state.changes if c.kind == "rewrite")
    assert rw.before.startswith("Worked on the backend")
    assert "Docker" not in rw.keywords  # claimed keyword not actually in the text is dropped
    assert state.projected["score"] > state.baseline["score"]
    assert state.summary.startswith("Rewrote")

    # Accept only the rewrite: the rest of the resume is untouched
    final = apply_changes(original, state.changes, {rw.id: {"action": "accept"}})
    assert final.find_bullet("s2e1b1")[2].text.startswith("Built REST APIs")
    assert final.find_entry("s2e2") is not None  # remove was not accepted
    # Edit a change
    final2 = apply_changes(original, state.changes, {rw.id: {"action": "edit", "text": "My own words."}})
    assert final2.find_bullet("s2e1b1")[2].text == "My own words."


def test_rewrite_of_unknown_bullet_and_limit_on_questions():
    state = start_state(parse_rules(RESUME), job(), JD, llm_used=True)
    ctx = Context([])
    assert execute("rewrite_bullet", {"bullet_id": "nope", "new_text": "x", "reason": ""}, state, ctx)["ok"] is False
    llm = FakeLLM(turns=[
        model(call("ask_user", questions=[{"question": f"Q{i}?"} for i in range(5)])),
    ])
    assert run(state, llm, ctx) == "needs_input"
    assert len(state.questions) == 3


def test_agent_survives_model_failure():
    from app.tailor.llm import LLMError

    class Broken(FakeLLM):
        def generate(self, *a, **k):
            raise LLMError("429")

    state = start_state(parse_rules(RESUME), job(), JD, llm_used=True)
    assert run(state, Broken(), Context([])) == "review"
    assert state.projected["score"] == state.baseline["score"]


def test_agent_nudged_once_when_it_finishes_without_changes():
    from app.tailor.agent import describe_llm_error

    state = start_state(parse_rules(RESUME), job(), JD, llm_used=True)
    fake = FakeLLM(turns=[
        {"role": "model", "parts": [{"functionCall": {"name": "finish", "args": {"summary": "Looks good already."}}}]},
        {"role": "model", "parts": [{"functionCall": {"name": "reorder", "args": {"container_id": "x", "ordered_ids": [], "reason": "r"}}}]},
        {"role": "model", "parts": [{"text": "done"}]},
    ])
    assert run(state, fake, Context([])) == "review"
    assert state.nudged and any(s.tool == "nudge" for s in state.steps)
    assert "haven't changed" in fake.calls[1]["parts"][-1]["text"]
    assert len(fake.turns) == 0  # second no-change stop is accepted, no infinite loop
    assert "daily quota" in describe_llm_error("Gemini 429 daily quota exhausted")
    assert "rate limit" in describe_llm_error("Gemini 429: x")
    assert "timed out" in describe_llm_error("Gemini timeout after 90s")


def test_model_failure_records_reason():
    from app.tailor.llm import LLMError

    class Broken(FakeLLM):
        def generate(self, *a, **k):
            raise LLMError("Gemini 429 daily quota exhausted")

    state = start_state(parse_rules(RESUME), job(), JD, llm_used=True)
    run(state, Broken(), Context([]))
    assert not state.changes and "daily quota" in state.llm_error
