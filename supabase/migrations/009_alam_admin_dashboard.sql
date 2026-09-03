-- Private ALAM admin analytics payload.
-- Public application roles cannot execute this SECURITY DEFINER function.

create or replace function public.alam_admin_dashboard()
returns jsonb
language sql
security definer
set search_path = ''
as $$
with
session_stats as (
    select
        e.session_id,
        min(e.created_at) as started_at,
        max(e.created_at) as ended_at,
        extract(epoch from (max(e.created_at) - min(e.created_at)))::numeric as duration_seconds,
        count(*)::bigint as event_count,
        min(e.visitor_id::text)::uuid as visitor_id
    from public.app_events e
    where e.session_id is not null and btrim(e.session_id) <> ''
    group by e.session_id
),
visitor_session_counts as (
    select visitor_id, count(distinct session_id)::bigint as sessions
    from public.app_events
    where visitor_id is not null and session_id is not null
    group by visitor_id
),
days as (
    select generate_series(
        (timezone('Asia/Tokyo', now())::date - 13)::timestamp,
        timezone('Asia/Tokyo', now())::date::timestamp,
        interval '1 day'
    )::date as day
),
daily as (
    select
        d.day,
        count(distinct e.visitor_id)::bigint as visitors,
        count(distinct e.session_id)::bigint as sessions,
        count(e.id)::bigint as events,
        count(e.id) filter (where e.event_name = 'article_open')::bigint as article_opens
    from days d
    left join public.app_events e
      on timezone('Asia/Tokyo', e.created_at)::date = d.day
    group by d.day
),
event_mix as (
    select event_name, count(*)::bigint as events,
           count(distinct visitor_id)::bigint as visitors,
           count(distinct session_id)::bigint as sessions
    from public.app_events
    group by event_name
    order by count(*) desc
),
page_mix as (
    select
        coalesce(nullif(properties->>'page',''), '(unknown)') as page,
        coalesce(nullif(properties->>'section',''), 'main') as section,
        count(*)::bigint as events,
        count(distinct visitor_id)::bigint as visitors
    from public.app_events
    where event_name = 'navigation'
    group by 1,2
    order by count(*) desc
),
platform_rows as (
    select
        case
            when coalesce(metadata->>'user_agent','') ~* '(iphone|ipad|ipod)' then 'iOS/iPadOS'
            when coalesce(metadata->>'user_agent','') ~* 'android' then 'Android'
            when coalesce(metadata->>'user_agent','') ~* 'windows' then 'Windows'
            when coalesce(metadata->>'user_agent','') ~* '(macintosh|mac os x)' then 'macOS'
            when coalesce(metadata->>'user_agent','') ~* '(linux|x11)' then 'Linux'
            else 'Other/Unknown'
        end as platform,
        count(*)::bigint as devices
    from public.visitor_devices
    group by 1
    order by count(*) desc
),
top_articles as (
    select
        a.id,
        a.title,
        a.category,
        count(e.id)::bigint as opens,
        count(distinct e.visitor_id)::bigint as readers,
        max(e.created_at) as last_opened_at
    from public.app_events e
    join public.articles a on a.id = e.article_id
    where e.event_name = 'article_open'
    group by a.id, a.title, a.category
    order by count(e.id) desc, max(e.created_at) desc
    limit 20
),
visitor_rows as (
    select
        vp.display_name,
        vp.created_at,
        vp.last_seen_at,
        vp.interaction_count,
        (select count(distinct ae.session_id) from public.app_events ae where ae.visitor_id = vp.id and ae.session_id is not null)::bigint as sessions,
        (select count(*) from public.app_events ae where ae.visitor_id = vp.id)::bigint as events,
        coalesce((
            select string_agg(distinct
                case
                    when coalesce(vd.metadata->>'user_agent','') ~* '(iphone|ipad|ipod)' then 'iOS/iPadOS'
                    when coalesce(vd.metadata->>'user_agent','') ~* 'android' then 'Android'
                    when coalesce(vd.metadata->>'user_agent','') ~* 'windows' then 'Windows'
                    when coalesce(vd.metadata->>'user_agent','') ~* '(macintosh|mac os x)' then 'macOS'
                    when coalesce(vd.metadata->>'user_agent','') ~* '(linux|x11)' then 'Linux'
                    else 'Other/Unknown'
                end, ', ')
            from public.visitor_devices vd
            where vd.visitor_id = vp.id
        ), 'Unknown') as platform
    from public.visitor_profiles vp
    order by vp.last_seen_at desc
    limit 200
),
recent_runs as (
    select
        ar.id,
        coalesce(ag.name, ar.agent_id) as agent,
        ar.agent_id,
        ar.started_at,
        ar.finished_at,
        ar.status,
        ar.stories_found,
        ar.stories_published,
        ar.stories_rejected,
        case when ar.finished_at is not null then extract(epoch from (ar.finished_at - ar.started_at))::numeric else null end as duration_seconds,
        ar.error_message
    from public.agent_runs ar
    left join public.agents ag on ag.slug = ar.agent_id
    order by ar.started_at desc
    limit 50
),
agent_summary as (
    select
        coalesce(ag.name, ar.agent_id) as agent,
        ar.agent_id,
        count(*)::bigint as runs,
        count(*) filter (where ar.status='success')::bigint as success,
        count(*) filter (where ar.status='partial')::bigint as partial,
        count(*) filter (where ar.status='failed')::bigint as failed,
        count(*) filter (where ar.status='running')::bigint as running,
        coalesce(sum(ar.stories_published),0)::bigint as stories_published,
        max(ar.started_at) as last_run_at
    from public.agent_runs ar
    left join public.agents ag on ag.slug = ar.agent_id
    group by coalesce(ag.name, ar.agent_id), ar.agent_id
    order by max(ar.started_at) desc
),
recent_articles as (
    select id,title,category,status,lifecycle_status,published_at,updated_at,
           importance_score,confidence_score,urgency
    from public.articles
    order by coalesce(updated_at,published_at,created_at) desc
    limit 40
),
content_status as (
    select status, count(*)::bigint as articles
    from public.articles
    group by status
    order by status
),
prediction_status as (
    select status, count(*)::bigint as predictions
    from public.predictions
    group by status
    order by status
)
select jsonb_build_object(
    'generated_at', now(),
    'overview', jsonb_build_object(
        'visitors', (select count(*) from public.visitor_profiles),
        'devices', (select count(*) from public.visitor_devices),
        'accounts', (select count(*) from auth.users),
        'sessions', (select count(*) from session_stats),
        'events', (select count(*) from public.app_events),
        'active_today', (select count(distinct visitor_id) from public.app_events where visitor_id is not null and timezone('Asia/Tokyo', created_at)::date = timezone('Asia/Tokyo', now())::date),
        'active_7d', (select count(distinct visitor_id) from public.app_events where visitor_id is not null and created_at >= now() - interval '7 days'),
        'active_30d', (select count(distinct visitor_id) from public.app_events where visitor_id is not null and created_at >= now() - interval '30 days'),
        'returning_visitors', (select count(*) from visitor_session_counts where sessions >= 2),
        'five_plus_session_visitors', (select count(*) from visitor_session_counts where sessions >= 5),
        'article_opens', (select count(*) from public.app_events where event_name='article_open'),
        'article_readers', (select count(distinct visitor_id) from public.app_events where event_name='article_open' and visitor_id is not null),
        'article_read_records', (select count(*) from public.article_reads),
        'saved_articles', (select count(*) from public.saved_articles),
        'feedback', (select count(*) from public.article_feedback),
        'published_articles', (select count(*) from public.articles where status='published'),
        'total_articles', (select count(*) from public.articles),
        'sources', (select count(*) from public.article_sources),
        'agent_comments', (select count(*) from public.agent_comments where status='published'),
        'agent_runs', (select count(*) from public.agent_runs),
        'failed_runs_24h', (select count(*) from public.agent_runs where status='failed' and started_at >= now()-interval '24 hours'),
        'first_event_at', (select min(created_at) from public.app_events),
        'last_event_at', (select max(created_at) from public.app_events),
        'last_agent_run_at', (select max(started_at) from public.agent_runs)
    ),
    'session_duration', jsonb_build_object(
        'avg_seconds', (select round(avg(duration_seconds),1) from session_stats),
        'median_seconds', (select round((percentile_cont(0.5) within group (order by duration_seconds))::numeric,1) from session_stats),
        'p90_seconds', (select round((percentile_cont(0.9) within group (order by duration_seconds))::numeric,1) from session_stats),
        'max_seconds', (select round(max(duration_seconds),1) from session_stats),
        'under_5s', (select count(*) from session_stats where duration_seconds < 5),
        's5_30', (select count(*) from session_stats where duration_seconds >=5 and duration_seconds <=30),
        's31_120', (select count(*) from session_stats where duration_seconds >30 and duration_seconds <=120),
        'over_120s', (select count(*) from session_stats where duration_seconds >120)
    ),
    'daily', coalesce((select jsonb_agg(to_jsonb(d) order by d.day) from daily d), '[]'::jsonb),
    'event_mix', coalesce((select jsonb_agg(to_jsonb(x)) from event_mix x), '[]'::jsonb),
    'page_mix', coalesce((select jsonb_agg(to_jsonb(x)) from page_mix x), '[]'::jsonb),
    'platforms', coalesce((select jsonb_agg(to_jsonb(x)) from platform_rows x), '[]'::jsonb),
    'top_articles', coalesce((select jsonb_agg(to_jsonb(x)) from top_articles x), '[]'::jsonb),
    'visitors', coalesce((select jsonb_agg(to_jsonb(x)) from visitor_rows x), '[]'::jsonb),
    'recent_agent_runs', coalesce((select jsonb_agg(to_jsonb(x)) from recent_runs x), '[]'::jsonb),
    'agent_summary', coalesce((select jsonb_agg(to_jsonb(x)) from agent_summary x), '[]'::jsonb),
    'recent_articles', coalesce((select jsonb_agg(to_jsonb(x)) from recent_articles x), '[]'::jsonb),
    'content_status', coalesce((select jsonb_agg(to_jsonb(x)) from content_status x), '[]'::jsonb),
    'prediction_status', coalesce((select jsonb_agg(to_jsonb(x)) from prediction_status x), '[]'::jsonb),
    'system', jsonb_build_object(
        'article_reads_instrumented', ((select count(*) from public.article_reads) > 0),
        'saves_instrumented', ((select count(*) from public.saved_articles) > 0),
        'feedback_instrumented', ((select count(*) from public.article_feedback) > 0),
        'media_assets', (select count(*) from public.media_assets),
        'notifications', (select count(*) from public.notifications),
        'daily_briefings', (select count(*) from public.daily_briefings),
        'predictions', (select count(*) from public.predictions),
        'prediction_updates', (select count(*) from public.prediction_updates),
        'relationships', (select count(*) from public.article_relationships),
        'topics', (select count(*) from public.topics)
    )
);
$$;

revoke all on function public.alam_admin_dashboard() from public;
revoke all on function public.alam_admin_dashboard() from anon;
revoke all on function public.alam_admin_dashboard() from authenticated;
grant execute on function public.alam_admin_dashboard() to service_role;
