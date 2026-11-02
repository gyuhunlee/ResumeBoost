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
│       ├── main.py     routes: dashboard, applications, tailor, account delete, health
│       ├── routes_gmail.py  Gmail connect / callback / status / sync / disconnect, daily sync-all
│       ├── gmail/      client.py (OAuth + Gmail API), classify.py, matching.py, sync.py
│       ├── tracker.py  builds Applications + Dashboard data from the database
│       ├── db.py       thin Supabase REST client (service key, server only)
│       ├── schemas.py  Pydantic models (snake_case in Python, camelCase in JSON)
│       └── mock_data.py
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

## Gmail tracker

How it works (`backend/app/gmail/`):

```
fetch new message IDs → prefilter (free) → classify (Gemini, or keyword rules) → match → upsert
```

- **When it syncs.** No always-on worker (Render's free plan sleeps). A sync runs when the Dashboard
  or Applications page opens and the last sync is over 15 minutes old, when the user clicks
  **Sync now**, and once a day for everyone via `.github/workflows/daily-gmail-sync.yml`.
- **Where it left off.** The first sync searches mail received since sign-up. After that, Gmail's
  `history` API returns only messages added after the stored `historyId`. If that id has expired
  (about a week), it falls back to a date search.
- **No duplicates.** Tailored resumes and inbox emails share one `applications` row, matched on a
  normalized company name plus a fuzzy role match (`matching.py`). `email_events` has a unique
  `(user_id, gmail_message_id)`, so re-reading an email can't double-count it. Uncertain matches
  are flagged `needs_review`.
- **Statuses.** Emails apply oldest first; a late "we received your application" never overwrites
  an interview, offer or rejection. `applied` with no news for 7 days shows as **Follow up**.
- **Privacy.** Read-only scope, refresh tokens encrypted with Fernet, email bodies never stored,
  and the `gmail_accounts` table has RLS with no policies (backend only).

### Setup

1. Run `backend/supabase/002_applications_gmail.sql` in the Supabase SQL editor.
2. Google Cloud Console → enable the **Gmail API**. On the OAuth consent screen add the
   `gmail.readonly` scope and add yourself (and testers) as **test users**. `gmail.readonly` is a
   restricted scope, so leave the app in Testing (up to 100 test users) unless you go through
   Google's verification.
3. In the OAuth client, add redirect URIs `http://localhost:8000/api/gmail/callback` and
   `https://<your-render-app>.onrender.com/api/gmail/callback`.
4. Set the new backend env vars (see `backend/.env.example`) locally and on Render.
5. GitHub → Settings → Secrets → Actions: add `API_URL` and `CRON_SECRET`.

Note: while the OAuth app is in Testing, Google expires refresh tokens after 7 days. The UI shows
"Reconnect Gmail" when that happens.

## Delete account

Settings → Delete account calls `DELETE /api/account`, which revokes Gmail access, deletes the
user's files in Storage, then deletes the Supabase auth user. Every table references
`auth.users ON DELETE CASCADE`, so all rows go with it.

## Next steps

- Replace `extract_keywords` and the mock rewrites in `backend/app/main.py` with LLM calls
  (Gemini via Google AI Studio or Groq both have free tiers). Keep the rule that the agent
  only rephrases facts already on the resume.
- Resume upload + parsing (PDF/DOCX) and PDF export.
