-- ALAM.ph public sync-health hardening.
--
-- The public health RPC previously returned a NULL sync status whenever no
-- `alam_supabase_sync` telemetry row existed, even if published articles had clearly
-- been written to Supabase. It could also report an older successful sync while newer
-- article mutations happened outside that tracked run. Both cases make the readiness
-- surface unable to distinguish "never synchronized" from "live data changed without
-- canonical sync telemetry".
--
-- Keep the existing RPC shape for backwards compatibility. The synthetic `untracked`
-- status is not written to public.agent_runs (whose canonical statuses remain running,
-- success, partial and failed); it is only a public diagnostic classification.

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
set search_path = ''
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
  ),
  health as (
    select
      ls.status,
      ls.started_at,
      ls.finished_at,
      ls.stories_found,
      ls.stories_published,
      ls.stories_rejected,
      ls.safe_error_count,
      coalesce(s.published_count, 0) as published_count,
      s.newest_update,
      case
        when s.newest_update is null then false
        when ls.started_at is null then true
        -- A small tolerance prevents harmless commit/database clock skew from being
        -- classified as drift while still exposing genuinely newer untracked writes.
        when s.newest_update > coalesce(ls.finished_at, ls.started_at) + interval '5 minutes' then true
        else false
      end as has_untracked_public_write
    from article_summary s
    left join latest_sync ls on true
  )
  select
    case when h.has_untracked_public_write then 'untracked' else h.status end,
    h.started_at,
    h.finished_at,
    coalesce(h.stories_found, 0),
    coalesce(h.stories_published, 0),
    coalesce(h.stories_rejected, 0),
    coalesce(h.safe_error_count, 0),
    h.published_count,
    h.newest_update
  from health h;
$$;

revoke all on function public.alam_public_sync_health() from public;
grant execute on function public.alam_public_sync_health() to anon, authenticated;

comment on function public.alam_public_sync_health() is
  'Public-safe ALAM sync snapshot. Returns untracked when published data is newer than canonical alam_supabase_sync telemetry; no private run metadata is exposed.';
