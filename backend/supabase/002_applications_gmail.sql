-- Migration 002: applications, Gmail sync, account deletion.
-- Run once in the Supabase SQL editor after schema.sql.
--
-- Every table references auth.users ON DELETE CASCADE, so deleting the auth user
-- (DELETE /api/account) removes all of a user's rows in one step.

-- 1. Applications ------------------------------------------------------------
-- One row per job. A row can start from either side and the two are merged:
--   source = 'tailored'  created by the tailor flow; status is NULL until an email confirms it
--   source = 'gmail'     found in the inbox; no job description or tailored resume
--   source = 'both'      tailored here AND confirmed by email
create table public.applications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  company text not null,
  company_norm text not null,          -- lowercased, no "Inc"/"LLC", for matching
  role text not null default '',
  role_norm text not null default '',
  status text check (status in ('applied', 'interviewing', 'offer', 'rejected')),
  source text not null default 'gmail' check (source in ('tailored', 'gmail', 'both')),
  job_description text,
  tailored_resume_path text,           -- storage path of the generated PDF; NULL disables "Download PDF"
  ats_score smallint check (ats_score between 0 and 100),
  applied_at timestamptz,
  status_updated_at timestamptz,       -- received time of the email that set the status
  needs_review boolean not null default false,  -- email matched, but not with certainty
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index applications_user_company_idx on public.applications (user_id, company_norm);

-- 2. Emails that changed an application -----------------------------------------
-- Only metadata is kept; email bodies are never stored.
create table public.email_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  gmail_message_id text not null,
  thread_id text,
  type text not null check (type in ('applied', 'interviewing', 'offer', 'rejected')),
  subject text not null default '',
  sender text not null default '',
  received_at timestamptz not null,    -- Gmail's internalDate, not when we processed it
  interview_at timestamptz,            -- when an interview email names a date and time
  confidence real,
  processed_at timestamptz not null default now(),
  unique (user_id, gmail_message_id)   -- reprocessing an email can never create a duplicate
);
create index email_events_app_idx on public.email_events (application_id, received_at);
create index email_events_user_idx on public.email_events (user_id, received_at);

-- 3. Gmail connection + sync cursor ----------------------------------------------
-- Holds the encrypted refresh token, so the browser must never read it:
-- RLS is on with NO policies; only the backend (service key) touches this table.
create table public.gmail_accounts (
  user_id uuid primary key references auth.users(id) on delete cascade,
  gmail_address text not null,
  refresh_token_encrypted text not null,
  history_id text,                     -- Gmail's cursor: next sync starts here
  last_synced_at timestamptz,
  sync_status text not null default 'idle' check (sync_status in ('idle', 'running', 'error')),
  sync_started_at timestamptz,
  last_error text,
  connected_at timestamptz not null default now()
);

-- 4. Row-level security -------------------------------------------------------
alter table public.applications   enable row level security;
alter table public.email_events   enable row level security;
alter table public.gmail_accounts enable row level security;

create policy "read own applications" on public.applications
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "read own email events" on public.email_events
  for select to authenticated using ((select auth.uid()) = user_id);

create trigger applications_touch before update on public.applications
  for each row execute function public.touch_updated_at();
