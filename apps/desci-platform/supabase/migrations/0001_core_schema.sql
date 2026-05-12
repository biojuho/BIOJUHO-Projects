create extension if not exists pgcrypto;

create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  firebase_uid text unique,
  email text unique,
  display_name text,
  wallet_address text,
  role text not null default 'researcher'
    check (role in ('researcher', 'vc', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists rfp_notices (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  title text not null,
  url text unique,
  deadline timestamptz,
  budget_range text,
  min_trl integer,
  max_trl integer,
  body_text text not null default '',
  keywords text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  collected_at timestamptz not null default now()
);

create table if not exists research_assets (
  id uuid primary key default gen_random_uuid(),
  owner_profile_id uuid references profiles(id) on delete set null,
  asset_type text not null default 'paper',
  title text not null,
  abstract text,
  ipfs_cid text,
  ipfs_url text,
  storage_path text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists match_results (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references profiles(id) on delete cascade,
  notice_id uuid references rfp_notices(id) on delete cascade,
  asset_id uuid references research_assets(id) on delete set null,
  fit_score integer not null check (fit_score between 0 and 100),
  fit_grade text not null check (fit_grade in ('S', 'A', 'B', 'C', 'D')),
  summary jsonb not null default '[]'::jsonb,
  risk_flags jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists subscriptions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references profiles(id) on delete cascade,
  tier text not null default 'free' check (tier in ('free', 'pro', 'enterprise')),
  stripe_customer_id text,
  stripe_subscription_id text,
  status text not null default 'inactive',
  current_period_end timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists governance_proposals (
  id uuid primary key default gen_random_uuid(),
  creator_profile_id uuid references profiles(id) on delete set null,
  proposer text,
  title text not null,
  description text not null default '',
  status text not null default 'active'
    check (status in ('draft', 'active', 'passed', 'rejected', 'archived')),
  votes_for integer not null default 0,
  votes_against integer not null default 0,
  end_time timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_profile_id uuid references profiles(id) on delete set null,
  event_type text not null,
  entity_type text,
  entity_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_rfp_notices_source_deadline
  on rfp_notices (source, deadline);

create index if not exists idx_research_assets_owner
  on research_assets (owner_profile_id, created_at desc);

create index if not exists idx_match_results_profile
  on match_results (profile_id, created_at desc);

create index if not exists idx_audit_events_type_created
  on audit_events (event_type, created_at desc);
