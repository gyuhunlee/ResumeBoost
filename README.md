# Resumeboost — AI resume improver

Portfolio project: an AI agent that tailors a resume to a job description (ATS-focused),
researches the company, and tracks applications from Gmail.

```
resumeboost/
├── frontend/          React + TypeScript (Vite, Tailwind CSS v4, React Router)
│   └── src/
│       ├── pages/     Landing.tsx, Dashboard.tsx, Applications.tsx, Tailor.tsx, Settings.tsx
│       ├── components/ AppLayout (sidebar), Logo, Icons, ui (Card, Chip, StatusPill, ScoreRing…)
│       ├── lib/api.ts  typed fetch client
│       ├── data/mock.ts sample data (used when the API is offline)
│       └── types.ts    shared shapes (mirror backend/app/schemas.py)
├── backend/           Python FastAPI
│   └── app/
│       ├── main.py     routes: GET /api/dashboard, GET /api/applications, GET /api/health
│       ├── routes_tailor.py  /api/tailor/sessions… (start, poll, answer, finalize)
│       ├── tailor/     the resume-tailoring agent and its tools (see below)
│       ├── schemas.py  Pydantic models (snake_case in Python, camelCase in JSON)
└── render.yaml        one-click deploy of the API to Render's free plan
```

## Run locally

Requires Node 20.19+ and Python 3.11+.

```bash
# 1) Backend
cd backend
py -m venv .venv                                     # Windows: .venv\Scripts\activate
source .venv/Scripts/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000        # docs at http://localhost:8000/docs

# 2) Frontend (new terminal)
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

In dev, Vite proxies `/api` to `localhost:8000`, so no CORS setup is needed.
If the backend isn't running, the pages fall back to sample data.

Routes: `/` landing · `/dashboard` overview (status ring, calendar, reminders) · `/applications` application table · `/tailor` tailoring flow.

## Deploy (free)

1. **Database + auth — Supabase (Free plan).** Create a project, enable the Google provider
   under Authentication, and replace the "Continue with Google" link in `Landing.tsx` with
   `supabase.auth.signInWithOAuth({ provider: "google" })`. Verify the Supabase JWT in FastAPI.
2. **API — Render (Free web service).** Push to GitHub, then *New → Blueprint* and pick the repo
   (`render.yaml` is included). Set `CORS_ORIGINS` to your frontend URL. Free services sleep
   when idle, so the first request after a while is slow.
3. **Frontend — Vercel (Hobby) or Cloudflare Pages.** Root directory `frontend`, build
   `npm run build`, output `dist`. Set `VITE_API_URL` to your Render URL.
   `vercel.json` handles client-side routing.

## Resume tailoring agent

`backend/app/tailor/` — code does what must be correct, the LLM does what needs judgment.

| Tool | Module | How |
|---|---|---|
| `parse_resume` | `parse.py` | LLM split into sections/bullets with ids; rejected (rule parser used) if it reworded anything |
| `analyze_job_description` | `jd.py` | LLM → required / preferred keywords; rule-based fallback |
| `keyword_gap`, `score_match` | `keywords.py` | Deterministic: exact / synonym / missing, weighted 0–100 score |
| `search_experience_bank`, `add_from_bank` | `bank.py`, `agent.py` | Experience bank (Settings) + the user's other resumes |
| `rewrite_bullet`, `reorder`, `remove_item` | `agent.py` | Recorded as changes against the original, never applied in place |
| `verify_claims` | `verify.py` | Hallucination guard: blocks unsupported numbers/skills, warns on unknown names |
| `check_format` | `formatting.py` | Length, weak/long bullets, missing sections |
| `ask_user` | `agent.py` | Pauses the run; answers resume it (state lives in `tailor_sessions`) |
| `render_resume` | `render.py` | PDF (reportlab) + DOCX (python-docx), single-column ATS layout |
| `save_tailored_resume` | `tracker.save_tailored` | Same company/role matching as the Gmail sync → no duplicates |

The agent loop runs Gemini function calling (`llm.py`, free tier) for at most 10 turns. Without
`GEMINI_API_KEY` the page still shows the keyword gap and score, just no rewrites.

Setup: run `backend/supabase/003_tailor_agent.sql` in the Supabase SQL editor. Optional env vars:
`TAILOR_MODEL` (defaults to `GEMINI_MODEL`) and `RESUME_FONT_PATH` (a `.ttf` such as DejaVuSans
for non-Latin characters in PDFs; without one, the PDF uses Helvetica).

Tests: `cd backend && python -m pytest -q` (the LLM is scripted, no network needed).

## Next steps

- Company research agent for the tailor page.
- Gmail tracker: Google OAuth with the `gmail.readonly` scope; classify confirmation/interview/
  rejection emails and update the application rows.
- Resume upload + parsing (PDF/DOCX) and PDF export.
