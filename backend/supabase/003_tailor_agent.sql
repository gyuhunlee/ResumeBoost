-- Migration 003: resume tailoring agent.
-- Run once in the Supabase SQL editor after 002_applications_gmail.sql.

-- 1. Experience bank ------------------------------------------------------------
-- Things the user has done that aren't necessarily on their resume. The agent can
-- search these and copy them in, and they count as "facts" for the claim checker.
create table public.experience_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  kind text not null default 'project'
    check (kind in ('job', 'project', 'education', 'volunteer', 'skill', 'other')),
  title text not null,
  organization text not null default '',
  dates text not null default '',
  bullets text[] not null default '{}',
  skills text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index experience_items_user_idx on public.experience_items (user_id);

alter table public.experience_items enable row level security;
create policy "manage own experience" on public.experience_items
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create trigger experience_items_touch before update on public.experience_items
  for each row execute function public.touch_updated_at();

-- 2. Tailoring sessions ------------------------------------------------------------
-- One row per "tailor this resume to this job" run. `state` holds the agent's
-- full state (parsed resume, proposed changes, questions, model conversation), so
-- the agent can pause on a question and resume in a later request.
-- RLS on with NO policies: only the backend (service key) reads or writes it.
create table public.tailor_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  resume_id uuid references public.resumes(id) on delete set null,
  company text not null,
  role text not null,
  status text not null default 'running'
    check (status in ('running', 'needs_input', 'review', 'finalized', 'error')),
  state jsonb,
  error text,
  application_id uuid references public.applications(id) on delete set null,
  pdf_path text,
  docx_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index tailor_sessions_user_idx on public.tailor_sessions (user_id, created_at desc);

alter table public.tailor_sessions enable row level security;

create trigger tailor_sessions_touch before update on public.tailor_sessions
  for each row execute function public.touch_updated_at();
