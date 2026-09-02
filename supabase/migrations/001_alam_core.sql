-- ALAM.ph core Supabase schema
-- Fresh-install migration. Existing public `agents` table is preserved.
-- `articles.status` is publication state. `articles.lifecycle_status` is the
-- ALAM story lifecycle (NEW/DEVELOPING/CONFIRMED/FADING/RESOLVED).

create extension if not exists pgcrypto;

create table if not exists public.articles (
  id text primary key,
  story_key text,
  category text not null,
  title text not null,
  summary text,
  status text not null default 'draft' check (status in ('draft','published','rejected','archived')),
  lifecycle_status text check (lifecycle_status is null or lifecycle_status in ('NEW','DEVELOPING','CONFIRMED','FADING','RESOLVED')),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  image_url text,
  image_type text check (image_type is null or image_type in ('real','official','editorial_generated','fallback')),
  importance_score numeric,
  confidence_score numeric,
  novelty_score numeric,
  urgency text,
  record jsonb not null default '{}'::jsonb
);

create index if not exists articles_status_published_idx on public.articles (status, published_at desc);
create index if not exists articles_category_published_idx on public.articles (category, published_at desc);
create index if not exists articles_story_key_idx on public.articles (story_key);
create index if not exists articles_lifecycle_idx on public.articles (lifecycle_status, published_at desc);
create index if not exists articles_record_gin_idx on public.articles using gin (record);

create table if not exists public.article_sources (
  id uuid primary key default gen_random_uuid(),
  article_id text not null references public.articles(id) on delete cascade,
  url text not null,
  publisher text,
  title text,
  published_at timestamptz,
  source_type text,
  is_primary boolean not null default false,
  reliability text,
  supports_claims jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  unique(article_id, url)
);
create index if not exists article_sources_article_idx on public.article_sources(article_id);

create table if not exists public.article_versions (
  id uuid primary key default gen_random_uuid(),
  article_id text not null references public.articles(id) on delete cascade,
  version_no integer not null,
  lifecycle_status text,
  change_summary text,
  record jsonb not null,
  created_at timestamptz not null default now(),
  unique(article_id, version_no)
);

create table if not exists public.agent_comments (
  id uuid primary key default gen_random_uuid(),
  article_id text not null references public.articles(id) on delete cascade,
  agent_id text not null,
  stance text,
  comment text not null,
  status text not null default 'published' check (status in ('draft','published','rejected')),
  created_at timestamptz not null default now()
);
create index if not exists agent_comments_article_idx on public.agent_comments(article_id, created_at);

create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent_id text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running','success','partial','failed')),
  stories_found integer not null default 0,
  stories_published integer not null default 0,
  stories_rejected integer not null default 0,
  error_message text,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists agent_runs_agent_started_idx on public.agent_runs(agent_id, started_at desc);

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

create table if not exists public.topics (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  label text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.article_topics (
  article_id text not null references public.articles(id) on delete cascade,
  topic_id uuid not null references public.topics(id) on delete cascade,
  weight numeric not null default 1,
  primary key(article_id, topic_id)
);

create table if not exists public.media_assets (
  id uuid primary key default gen_random_uuid(),
  article_id text references public.articles(id) on delete cascade,
  asset_type text not null check (asset_type in ('real','official','editorial_generated','fallback')),
  storage_path text,
  public_url text,
  source_url text,
  alt_text text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists media_assets_article_idx on public.media_assets(article_id, created_at desc);

create table if not exists public.user_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  interests jsonb not null default '{}'::jsonb,
  muted_topics jsonb not null default '[]'::jsonb,
  language text not null default 'taglish',
  settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.saved_articles (
  user_id uuid not null references auth.users(id) on delete cascade,
  article_id text not null references public.articles(id) on delete cascade,
  collection text not null default 'saved',
  created_at timestamptz not null default now(),
  primary key(user_id, article_id)
);

create table if not exists public.article_reads (
  id bigint generated by default as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  article_id text not null references public.articles(id) on delete cascade,
  opened_at timestamptz not null default now(),
  seconds_read integer,
  completed boolean not null default false
);
create index if not exists article_reads_user_opened_idx on public.article_reads(user_id, opened_at desc);

create table if not exists public.article_feedback (
  user_id uuid not null references auth.users(id) on delete cascade,
  article_id text not null references public.articles(id) on delete cascade,
  feedback text not null check (feedback in ('useful','not_useful','more_like_this','less_like_this','not_for_me')),
  created_at timestamptz not null default now(),
  primary key(user_id, article_id, feedback)
);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  article_id text references public.articles(id) on delete cascade,
  kind text not null,
  title text not null,
  body text,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists notifications_user_created_idx on public.notifications(user_id, created_at desc);

create table if not exists public.daily_briefings (
  id uuid primary key default gen_random_uuid(),
  briefing_date date not null,
  user_id uuid references auth.users(id) on delete cascade,
  content jsonb not null,
  created_at timestamptz not null default now()
);
create unique index if not exists daily_briefings_user_day_idx
  on public.daily_briefings(briefing_date, user_id) where user_id is not null;
create unique index if not exists daily_briefings_public_day_idx
  on public.daily_briefings(briefing_date) where user_id is null;

create table if not exists public.predictions (
  id uuid primary key default gen_random_uuid(),
  article_id text references public.articles(id) on delete set null,
  agent_id text not null,
  claim text not null,
  horizon text,
  confidence numeric,
  status text not null default 'open' check (status in ('open','correct','partially_correct','incorrect','unresolved')),
  resolution_notes text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

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

create table if not exists public.article_relationships (
  from_article_id text not null references public.articles(id) on delete cascade,
  to_article_id text not null references public.articles(id) on delete cascade,
  relationship text not null,
  strength numeric,
  explanation text,
  created_at timestamptz not null default now(),
  primary key(from_article_id, to_article_id, relationship)
);

create table if not exists public.app_events (
  id bigint generated by default as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  session_id text,
  event_name text not null,
  article_id text references public.articles(id) on delete set null,
  properties jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists app_events_created_idx on public.app_events(created_at desc);

-- Public media bucket for persisted article artwork. Uploads remain server-side only.
insert into storage.buckets (id, name, public)
values ('alam-media', 'alam-media', true)
on conflict (id) do update set public = excluded.public;

-- Public content is readable anonymously. Personal state is private to each user.
alter table public.articles enable row level security;
alter table public.article_sources enable row level security;
alter table public.article_versions enable row level security;
alter table public.agent_comments enable row level security;
alter table public.agent_runs enable row level security;
alter table public.rejected_candidates enable row level security;
alter table public.topics enable row level security;
alter table public.article_topics enable row level security;
alter table public.media_assets enable row level security;
alter table public.user_preferences enable row level security;
alter table public.saved_articles enable row level security;
alter table public.article_reads enable row level security;
alter table public.article_feedback enable row level security;
alter table public.notifications enable row level security;
alter table public.daily_briefings enable row level security;
alter table public.predictions enable row level security;
alter table public.prediction_updates enable row level security;
alter table public.article_relationships enable row level security;
alter table public.app_events enable row level security;

drop policy if exists "Public can read published articles" on public.articles;
create policy "Public can read published articles" on public.articles for select using (status = 'published');

drop policy if exists "Public can read article sources" on public.article_sources;
create policy "Public can read article sources" on public.article_sources for select using (
  exists (select 1 from public.articles a where a.id = article_id and a.status = 'published')
);

drop policy if exists "Public can read published comments" on public.agent_comments;
create policy "Public can read published comments" on public.agent_comments for select using (status = 'published');

drop policy if exists "Public can read topics" on public.topics;
create policy "Public can read topics" on public.topics for select using (true);

drop policy if exists "Public can read article topics" on public.article_topics;
create policy "Public can read article topics" on public.article_topics for select using (true);

drop policy if exists "Public can read media assets" on public.media_assets;
create policy "Public can read media assets" on public.media_assets for select using (
  article_id is null or exists (select 1 from public.articles a where a.id = article_id and a.status = 'published')
);

drop policy if exists "Public can read predictions" on public.predictions;
create policy "Public can read predictions" on public.predictions for select using (true);

drop policy if exists "Public can read prediction updates" on public.prediction_updates;
create policy "Public can read prediction updates" on public.prediction_updates for select using (true);

drop policy if exists "Public can read article relationships" on public.article_relationships;
create policy "Public can read article relationships" on public.article_relationships for select using (true);

drop policy if exists "Public can read alam media" on storage.objects;
create policy "Public can read alam media" on storage.objects for select using (bucket_id = 'alam-media');

drop policy if exists "Users manage own preferences" on public.user_preferences;
create policy "Users manage own preferences" on public.user_preferences for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users manage own saved articles" on public.saved_articles;
create policy "Users manage own saved articles" on public.saved_articles for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users manage own reads" on public.article_reads;
create policy "Users manage own reads" on public.article_reads for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users manage own feedback" on public.article_feedback;
create policy "Users manage own feedback" on public.article_feedback for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users read own notifications" on public.notifications;
create policy "Users read own notifications" on public.notifications for select using (auth.uid() = user_id);

drop policy if exists "Users update own notifications" on public.notifications;
create policy "Users update own notifications" on public.notifications for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users read own briefings" on public.daily_briefings;
create policy "Users read own briefings" on public.daily_briefings for select using (auth.uid() = user_id or user_id is null);

drop policy if exists "Users insert own app events" on public.app_events;
create policy "Users insert own app events" on public.app_events for insert with check (auth.uid() = user_id or user_id is null);

drop policy if exists "Users read own app events" on public.app_events;
create policy "Users read own app events" on public.app_events for select using (auth.uid() = user_id);

-- Intentionally no anonymous/client INSERT/UPDATE/DELETE policies for shared content,
-- agent runs, rejected candidates, article versions, or Storage uploads. Trusted agent
-- ingestion must use a server-side service role or Edge Function.
