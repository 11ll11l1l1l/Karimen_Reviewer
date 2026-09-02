-- ALAM.ph compatibility migration.
-- Run this ONLY if you already executed an earlier draft of 001_alam_core.sql.
-- It is idempotent and adds the lifecycle/media/quality pieces without deleting data.

alter table if exists public.articles
  add column if not exists lifecycle_status text;

alter table if exists public.article_sources
  add column if not exists title text;

alter table if exists public.article_versions
  add column if not exists lifecycle_status text;

create index if not exists articles_lifecycle_idx on public.articles (lifecycle_status, published_at desc);

create table if not exists public.rejected_candidates (
  id uuid primary key default gen_random_uuid(),
  agent_id text not null,
  candidate_key text,
  title text,
  reason text not null,
  quality_checks jsonb not null default '{}'::jsonb,
  candidate jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists rejected_candidates_created_idx on public.rejected_candidates(created_at desc);

create table if not exists public.media_assets (
  id uuid primary key default gen_random_uuid(),
  article_id text references public.articles(id) on delete cascade,
  asset_type text not null,
  storage_path text,
  public_url text,
  source_url text,
  alt_text text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists media_assets_article_idx on public.media_assets(article_id, created_at desc);

create table if not exists public.prediction_updates (
  id uuid primary key default gen_random_uuid(),
  prediction_id uuid not null references public.predictions(id) on delete cascade,
  previous_status text,
  new_status text,
  evidence jsonb not null default '[]'::jsonb,
  notes text,
  created_at timestamptz not null default now()
);
create index if not exists prediction_updates_prediction_idx on public.prediction_updates(prediction_id, created_at);

insert into storage.buckets (id, name, public)
values ('alam-media', 'alam-media', true)
on conflict (id) do update set public = excluded.public;

alter table public.rejected_candidates enable row level security;
alter table public.media_assets enable row level security;
alter table public.prediction_updates enable row level security;

drop policy if exists "Public can read media assets" on public.media_assets;
create policy "Public can read media assets" on public.media_assets for select using (
  article_id is null or exists (select 1 from public.articles a where a.id = article_id and a.status = 'published')
);

drop policy if exists "Public can read prediction updates" on public.prediction_updates;
create policy "Public can read prediction updates" on public.prediction_updates for select using (true);

drop policy if exists "Public can read alam media" on storage.objects;
create policy "Public can read alam media" on storage.objects for select using (bucket_id = 'alam-media');
