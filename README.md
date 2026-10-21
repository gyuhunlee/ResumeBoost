# Resumeboost — AI resume improver

Portfolio project: an AI agent that tailors a resume to a job description (ATS-focused),
researches the company, and tracks applications from Gmail.

```
resumeboost/
├── frontend/          React + TypeScript (Vite, Tailwind CSS v4, React Router)
│   └── src/
│       ├── pages/     Landing.tsx, Dashboard.tsx, Tailor.tsx
│       ├── components/ AppLayout (sidebar), Logo, Icons, ui (Card, Chip, StatusPill, ScoreRing…)
│       ├── lib/api.ts  typed fetch client
│       ├── data/mock.ts sample data (used when the API is offline)
│       └── types.ts    shared shapes (mirror backend/app/schemas.py)
├── backend/           Python FastAPI
│   └── app/
│       ├── main.py     routes: GET /api/applications, POST /api/tailor, GET /api/health
│       ├── schemas.py  Pydantic models (snake_case in Python, camelCase in JSON)
│       └── mock_data.py
└── render.yaml        one-click deploy of the API to Render's free plan
```

## Run locally

Requires Node 20.19+ and Python 3.11+.

```bash
# 1) Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000           # docs at http://localhost:8000/docs

# 2) Frontend (new terminal)
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

In dev, Vite proxies `/api` to `localhost:8000`, so no CORS setup is needed.
If the backend isn't running, the pages fall back to sample data.

Routes: `/` landing · `/dashboard` applications · `/tailor` tailoring flow.

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

## Next steps

- Replace `extract_keywords` and the mock rewrites in `backend/app/main.py` with LLM calls
  (Gemini via Google AI Studio or Groq both have free tiers). Keep the rule that the agent
  only rephrases facts already on the resume.
- Gmail tracker: Google OAuth with the `gmail.readonly` scope; classify confirmation/interview/
  rejection emails and update the application rows.
- Resume upload + parsing (PDF/DOCX) and PDF export.
