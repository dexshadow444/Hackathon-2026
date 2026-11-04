-- Run once in Supabase → SQL Editor.
-- All access happens from the FastAPI server using the service-role key.
-- RLS is enabled with no policies, so the public anon key can read nothing.

create extension if not exists pgcrypto;

-- ---------- Team code sequence (HACK-27-<seq>-<random>) ----------
create sequence if not exists team_code_seq start 101;

create or replace function next_team_seq() returns bigint
language sql as $$ select nextval('team_code_seq') $$;
revoke execute on function next_team_seq() from public, anon, authenticated;

-- ---------- updated_at trigger ----------
create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

-- ---------- registrations ----------
create table if not exists registrations (
  id                    uuid primary key default gen_random_uuid(),

  -- identity
  team_code             text not null unique,
  team_name             text not null check (char_length(team_name) between 1 and 128),
  team_name_key         text generated always as (lower(btrim(team_name))) stored,
  college_name          text not null check (char_length(college_name) between 1 and 256),
  track                 text not null,

  -- leader
  leader_name           text not null check (char_length(leader_name) between 1 and 128),
  leader_email          text not null,
  leader_phone          text not null check (leader_phone ~ '^[6-9][0-9]{9}$'),
  leader_department     text not null,
  leader_year           text not null,
  leader_gender         text,
  leader_id_number      text,

  -- members (2 to 5 members: 1 leader + 1 to 4 crew members)
  member_count          int  not null check (member_count between 2 and 5),
  members_data          jsonb not null default '[]'::jsonb,

  -- idea
  idea_title            text not null check (char_length(idea_title) <= 100),
  idea_summary          text not null check (char_length(idea_summary) <= 10000),
  idea_description      text not null check (char_length(idea_description) <= 50000),
  idea_ppt_filename     text,
  idea_ppt_path         text,
  google_drive_file_id  text,
  google_drive_web_link text,

  -- consent
  terms_accepted        boolean not null default false,
  terms_version         text,
  terms_accepted_at     timestamptz,

  -- payment
  amount_paid           numeric(10,2) not null default 0,
  payment_status        text not null default 'pending'
                        check (payment_status in ('pending','paid','failed')),
  payment_mode          text,
  razorpay_order_id     text,
  razorpay_payment_id   text,
  razorpay_signature    text,
  payment_timestamp     timestamptz,

  -- review
  review_status         text not null default 'submitted'
                        check (review_status in ('submitted','under_review','shortlisted','waitlist','rejected')),
  admin_notes           text,

  -- audit
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- case-insensitive unique team name
create unique index if not exists registrations_team_name_key_uq on registrations (team_name_key);
create index if not exists registrations_payment_status_idx on registrations (payment_status);
create index if not exists registrations_track_idx          on registrations (track);
create index if not exists registrations_review_status_idx  on registrations (review_status);

drop trigger if exists trg_registrations_updated on registrations;
create trigger trg_registrations_updated before update on registrations
  for each row execute function set_updated_at();

alter table registrations enable row level security;

-- ---------- Admin Action Audit Trail Table ----------
create table if not exists admin_audit_logs (
  id              uuid primary key default gen_random_uuid(),
  registration_id text not null,
  team_code       text,
  team_name       text,
  admin_user      text not null,
  action_type     text not null,
  changes_json    jsonb not null default '{}'::jsonb,
  notes           text,
  created_at      timestamptz not null default now()
);
create index if not exists admin_audit_reg_idx on admin_audit_logs (registration_id);
create index if not exists admin_audit_created_idx on admin_audit_logs (created_at desc);
alter table admin_audit_logs enable row level security;

-- ---------- "Notify me" leads ----------
create table if not exists preregistration_alerts (
  id             uuid primary key default gen_random_uuid(),
  full_name      text not null,
  email          text not null,
  email_key      text generated always as (lower(btrim(email))) stored,
  college        text not null,
  track_interest text not null,
  created_at     timestamptz not null default now()
);
create unique index if not exists preregistration_alerts_email_uq on preregistration_alerts (email_key);
alter table preregistration_alerts enable row level security;

-- ---------- Private storage bucket for idea presentations ----------
insert into storage.buckets (id, name, public)
values ('hackathon-ideas', 'hackathon-ideas', false)
on conflict (id) do update set public = false;
