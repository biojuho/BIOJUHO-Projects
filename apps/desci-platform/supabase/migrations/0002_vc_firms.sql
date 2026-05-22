-- vc_firms: curated biotech VC dataset (KR + global)
-- Source of truth: apps/desci-platform/backend/data/vcs_seed.json
-- Seeded by: apps/desci-platform/backend/scripts/seed_vcs.py
-- Additive only — no edits to existing tables.

create table if not exists vc_firms (
  id text primary key,
  name text not null,
  country text not null default 'KR' check (length(country) = 2),
  website text,
  investment_thesis text not null,
  preferred_stages text[] not null default '{}',
  portfolio_keywords text[] not null default '{}',
  contact_email text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_vc_firms_country
  on vc_firms (country);

create index if not exists idx_vc_firms_keywords_gin
  on vc_firms using gin (portfolio_keywords);

create index if not exists idx_vc_firms_stages_gin
  on vc_firms using gin (preferred_stages);
