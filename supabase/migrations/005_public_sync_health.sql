-- ALAM.ph public-safe synchronization health snapshot.
--
-- RLS intentionally prevents anonymous/public clients from reading public.agent_runs
-- because that table can contain operator metadata and private error diagnostics.
-- This SECURITY DEFINER function exposes only a deliberately small aggregate surface
-- needed by the public Settings/readiness view. It does not return metadata, raw
-- errors, GitHub actor/repository identifiers, workflow URLs, secrets, or any private
-- Global Engineering Job Radar information.

create or replace function public.alam_public_sync_health()
returns table (
  last_sync_status text,
  last_sync_started_at timestamptz,
  last_sync_finished_at timestamptz,
  stories_found integer,
  stories_published integer,
  stories_rejected integer,
  error_count integer,
  published_articles bigint,
  latest_article_updated_at timestamptz
)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  with latest_sync as (
    select
      ar.status,
      ar.started_at,
      ar.finished_at,
      ar.stories_found,
      ar.stories_published,
      ar.stories_rejected,
      case
        when jsonb_typeof(ar.metadata) = 'object'
          and (ar.metadata ->> 'error_count') ~ '^[0-9]+$'
        then (ar.metadata ->> 'error_count')::integer
        else 0
      end as safe_error_count
    from public.agent_runs ar
    where ar.agent_id = 'alam_supabase_sync'
    order by ar.started_at desc
    limit 1
  ),
  article_summary as (
    select
      count(*) filter (where a.status = 'published')::bigint as published_count,
      max(a.updated_at) filter (where a.status = 'published') as newest_update
    from public.articles a
  )
  select
    ls.status,
    ls.started_at,
    ls.finished_at,
    coalesce(ls.stories_found, 0),
    coalesce(ls.stories_published, 0),
    coalesce(ls.stories_rejected, 0),
    coalesce(ls.safe_error_count, 0),
    coalesce(s.published_count, 0),
    s.newest_update
  from article_summary s
  left join latest_sync ls on true;
$$;

-- SECURITY DEFINER is used narrowly here to cross the agent_runs RLS boundary. Keep
-- default PUBLIC execution revoked, then opt in only the two public app roles.
revoke all on function public.alam_public_sync_health() from public;
grant execute on function public.alam_public_sync_health() to anon, authenticated;

comment on function public.alam_public_sync_health() is
  'Public-safe ALAM deployment readiness snapshot. Exposes sanitized trusted-sync status and aggregate published-article freshness only.';
