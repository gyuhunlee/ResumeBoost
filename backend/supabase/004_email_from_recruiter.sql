-- Migration 004: remember whether an email came from a person or an automated system.
-- Run once in the Supabase SQL editor after 003_tailor_agent.sql.
--
-- NULL = recorded before this column existed; the API then guesses from the sender address.
alter table public.email_events add column if not exists from_recruiter boolean;
