-- 1. Tables
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  title text not null default 'My resume',
  file_name text,                      -- original file name, e.g. resume.pdf
  file_path text,                      -- path in the 'resumes' storage bucket
  content text not null default '',    -- extracted text the user can edit
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index resumes_user_id_idx on public.resumes (user_id);

-- 2. Row-level security: each user sees only their own rows
alter table public.profiles enable row level security;
alter table public.resumes  enable row level security;

create policy "read own profile" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "update own profile" on public.profiles
  for update to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

create policy "manage own resumes" on public.resumes
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Users may edit their name, but not their email
revoke update on public.profiles from authenticated;
grant update (full_name) on public.profiles to authenticated;

-- 3. Copy the Google name and photo into profiles on first sign-in
create function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'),
    coalesce(new.raw_user_meta_data ->> 'avatar_url', new.raw_user_meta_data ->> 'picture')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 4. Keep updated_at current
create function public.touch_updated_at()
returns trigger language plpgsql set search_path = ''
as $$ begin new.updated_at = now(); return new; end; $$;

create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();
create trigger resumes_touch before update on public.resumes
  for each row execute function public.touch_updated_at();

-- Private bucket: 5 MB limit, PDF and DOCX only
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'resumes', 'resumes', false, 5242880,
  array['application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
);

-- Users can read, upload, replace and delete only files in their own folder
create policy "manage own resume files" on storage.objects
  for all to authenticated
  using (bucket_id = 'resumes'
         and (storage.foldername(name))[1] = (select auth.uid())::text)
  with check (bucket_id = 'resumes'
              and (storage.foldername(name))[1] = (select auth.uid())::text);