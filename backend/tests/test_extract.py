"""Tests for pulling company / role / status out of application emails.

Run:  cd backend && python -m pytest -q tests/test_extract.py
"""

import pytest

from app.gmail.extract import (
    clean_body,
    company_supported,
    extract_company,
    extract_role,
    extract_status,
    is_bad_company,
)

# (sender, subject, body, company, role, status)
CASES = [
    pytest.param(
        "Jane Kim <jane.kim@northwindhealth.com>",
        "Next steps for your application",
        "Hi Gyuhun,\nThanks for applying to Northwind Health for the Data Analyst position. "
        "I'd like to schedule a 30-minute phone screen. Please share your availability for next week.\n"
        "Best,\nJane Kim\nTalent Partner, Northwind Health",
        "Northwind Health", "Data Analyst", "interviewing",
        id="recruiter-person-is-not-the-company",
    ),
    pytest.param(
        "Greenhouse <no-reply@us.greenhouse-mail.io>",
        "Thank you for applying to Acme",
        "Hi Gyuhun,\nThank you for your interest in Acme! We've received your application for "
        "Software Engineer, Backend (Req #4521). Our team will review it and, if your qualifications "
        "match, we will reach out to schedule an interview.\nThe Acme Recruiting Team\n"
        "https://boards.greenhouse.io/acme/jobs/4521",
        "Acme", "Software Engineer, Backend", "applied",
        id="ats-confirmation-with-conditional-interview",
    ),
    pytest.param(
        "Workday <cityofdavis@myworkday.com>",
        "Application Received: Wastewater Treatment Plant Operator-in-Training",
        "Dear Gyuhun,\nThank you for applying for the Wastewater Treatment Plant Operator-in-Training "
        "position with the City of Davis. Your application has been received and will be reviewed.",
        "City of Davis", "Wastewater Treatment Plant Operator-in-Training", "applied",
        id="government-workday",
    ),
    pytest.param(
        "NEOGOV <noreply@governmentjobs.com>",
        "Sacramento County: Invitation to Written Examination",
        "Congratulations! You are invited to the written examination for Water Quality Technician I "
        "with Sacramento County on November 20.",
        "Sacramento County", "Water Quality Technician I", "interviewing",
        id="government-exam-invite",
    ),
    pytest.param(
        "Lever <no-reply@hire.lever.co>",
        "Your application to Globex",
        "Hi Gyuhun,\nThank you for your interest in the Frontend Engineer role at Globex. "
        "Unfortunately, we have decided to move forward with other candidates whose experience more "
        "closely matches our needs.\nBest,\nGlobex Talent Team",
        "Globex", "Frontend Engineer", "rejected",
        id="lever-rejection",
    ),
    pytest.param(
        "LinkedIn <jobs-noreply@linkedin.com>",
        "Your application was sent to Initech",
        "Your application was sent to Initech\nJunior Data Engineer\nInitech · San Jose, CA (Hybrid)",
        "Initech", "", "applied",
        id="linkedin-easy-apply",
    ),
    pytest.param(
        "Tom Park <tpark@lumenlabs.ai>",
        "Offer - Frontend Engineer",
        "Hi Gyuhun, I'm thrilled to share that we're pleased to offer you the Frontend Engineer position "
        "at Lumen Labs. Your offer letter is attached.\nTom",
        "Lumen Labs", "Frontend Engineer", "offer",
        id="offer-from-person",
    ),
    pytest.param(
        "Orbital Careers <careers@orbital.com>",
        "Interview invitation: Platform Engineer",
        "Hello,\nWe'd like to invite you to a virtual interview for the Platform Engineer role. "
        "Please pick a time using this link: https://calendly.com/orbital/interview",
        "Orbital", "Platform Engineer", "interviewing",
        id="display-name-company",
    ),
]


CASES += [
    pytest.param(
        "Sarah Lee <sarah.lee@gmail.com>",
        "Interview - Junior Developer at Brightpath",
        "Hi Gyuhun, are you free Thursday afternoon for a video interview? Sarah",
        "Brightpath", "Junior Developer", "interviewing",
        id="recruiter-on-free-mail",
    ),
    pytest.param(
        "Mike Chen <mike@brightpath.io>",
        "Re: Your application",
        "Hi, thanks for applying. We'd love to set up a call this week. What times work for you?",
        "Brightpath", "", "interviewing",
        id="company-only-in-domain",
    ),
    pytest.param(
        "Kestrel <no-reply@ashbyhq.com>",
        "Thanks for applying!",
        "We received your application for Junior ML Engineer and will be in touch.",
        "Kestrel", "Junior ML Engineer", "applied",
        id="ashby-display-name",
    ),
    pytest.param(
        "Atlas Health Careers <atlashealth@icims.com>",
        "Application confirmation",
        "Thank you for your interest in a career with Atlas Health. Job Title: Backend Engineer (Remote)\n"
        "Requisition ID: 2026-1182",
        "Atlas Health", "Backend Engineer", "applied",
        id="icims-job-title-line",
    ),
    pytest.param(
        "Greenhouse <no-reply@greenhouse.io>",
        "Thank you for your application",
        "We have received your application and will review it shortly.",
        "", "", "applied",
        id="no-company-anywhere-returns-blank",
    ),
    pytest.param(
        "Jane Kim <jane.kim@gmail.com>",
        "Quick question",
        "Hi Gyuhun, thank you for applying. Are you available for a quick call?",
        "", "", "interviewing",
        id="person-on-free-mail-never-becomes-company",
    ),
]


@pytest.mark.parametrize("sender,subject,body,company,role,status", CASES)
def test_extracts(sender, subject, body, company, role, status):
    got_company = extract_company(sender, subject, body)
    assert got_company == company
    assert extract_role(subject, body, got_company) == role
    assert extract_status(subject, body)[0] == status


def test_person_and_vendor_names_are_rejected():
    assert is_bad_company("Jane Kim", "Jane Kim <jane.kim@acme.com>")
    assert is_bad_company("Greenhouse")
    assert is_bad_company("Hiring Team")
    assert is_bad_company("Software Engineer")
    assert not is_bad_company("Acme Health")
    assert not is_bad_company("City of Davis")


def test_llm_answer_is_checked_against_the_email():
    sender = "Jane Kim <jane.kim@northwindhealth.com>"
    body = "Thanks for applying to Northwind Health. Let's schedule an interview."
    assert not company_supported("Jane Kim", sender, "Hi", body)          # person
    assert not company_supported("Greenhouse", sender, "Hi", body)        # vendor
    assert not company_supported("Contoso", sender, "Hi", body)           # made up
    assert company_supported("Northwind Health", sender, "Hi", body)


def test_quoted_reply_is_ignored():
    body = ("Sounds good, see you then!\n\nOn Mon, Nov 3, 2026 at 9:00 AM Jane <jane@acme.com> wrote:\n"
            "> Unfortunately we have to reschedule")
    assert "Unfortunately" not in clean_body(body)


def test_rescheduling_is_not_a_rejection():
    body = "Unfortunately I can't make Tuesday. Could we schedule the interview for Thursday instead?"
    assert extract_status("Re: Interview", body)[0] == "interviewing"
