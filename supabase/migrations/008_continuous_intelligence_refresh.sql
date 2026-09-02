-- ALAM.ph continuous derived-intelligence refresh.
-- This job never invents new factual claims. It derives durable state only from
-- already-published, validated ALAM records.

create extension if not exists pg_cron;

create schema if not exists internal;
revoke all on schema internal from public, anon, authenticated;

create or replace function internal.alam_refresh_intelligence()
returns void
language plpgsql
set search_path = public, pg_temp
as $$
declare
  v_today date := (now() at time zone 'Asia/Tokyo')::date;
begin
  -- Forecast accountability: persist exact forecast text already present in
  -- verified Market stories. New text creates a new ledger item; existing calls stay.
  with market_articles as (
    select id,
           coalesce(record->>'agent', category) as agent_id,
           confidence_score,
           record->'content' as content
    from public.articles
    where status='published' and category='reflection'
  ), forecasts as (
    select id as article_id, agent_id, confidence_score,
           'next_session'::text as horizon,
           content->>'forecast_next_session' as claim
      from market_articles
    union all
    select id, agent_id, confidence_score, '5_trading_days', content->>'forecast_5d'
      from market_articles
    union all
    select id, agent_id, confidence_score, '1_3_months', content->>'forecast_1_3m'
      from market_articles
  )
  insert into public.predictions(article_id,agent_id,claim,horizon,confidence,status)
  select f.article_id,f.agent_id,f.claim,f.horizon,f.confidence_score,'open'
    from forecasts f
   where nullif(btrim(f.claim),'') is not null
     and not exists (
       select 1 from public.predictions p
        where p.article_id=f.article_id
          and p.horizon=f.horizon
          and p.claim=f.claim
     );

  -- Connect the Dots: deterministic shared-signal overlap only. This is not a
  -- causal inference and the relationship label deliberately says shared_signal.
  delete from public.article_relationships where relationship='shared_signal';

  with tags as (
    select a.id,
           jsonb_array_elements_text(
             coalesce(a.record->'content'->'connection_tags','[]'::jsonb)
           ) as tag
      from public.articles a
     where a.status='published'
  ), pairs as (
    select least(t1.id,t2.id) as a_id,
           greatest(t1.id,t2.id) as b_id,
           array_agg(distinct t1.tag order by t1.tag) as shared_tags,
           count(distinct t1.tag)::numeric as overlap_count
      from tags t1
      join tags t2 on t1.tag=t2.tag and t1.id<>t2.id
     group by least(t1.id,t2.id), greatest(t1.id,t2.id)
  ), unions as (
    select p.*,
           (select count(distinct tag)::numeric
              from tags t where t.id in (p.a_id,p.b_id)) as union_count
      from pairs p
  )
  insert into public.article_relationships(
    from_article_id,to_article_id,relationship,strength,explanation
  )
  select a_id,b_id,'shared_signal',
         round(overlap_count/nullif(union_count,0),3),
         'Shared signal tags: ' || array_to_string(shared_tags, ', ')
    from unions
   where overlap_count >= 1;

  -- Persist one global 5-minute briefing per Japan calendar day. The briefing
  -- stores story references, not freshly generated factual prose.
  delete from public.daily_briefings
   where briefing_date=v_today and user_id is null;

  insert into public.daily_briefings(briefing_date,user_id,content)
  values (
    v_today,
    null,
    jsonb_build_object(
      'generated_at', now(),
      'timezone', 'Asia/Tokyo',
      'things_to_know', coalesce((
        select jsonb_agg(id order by importance_score desc nulls last, published_at desc)
          from (
            select id, importance_score, published_at
              from public.articles
             where status='published'
             order by importance_score desc nulls last, published_at desc
             limit 3
          ) x
      ), '[]'::jsonb),
      'thing_to_do', (
        select id
          from public.articles
         where status='published'
           and category='practical'
           and upper(coalesce(record->'content'->>'action',''))
               in ('DO NOW','APPLY','PREPARE','AVOID')
         order by importance_score desc nulls last, published_at desc
         limit 1
      ),
      'risk_to_watch', (
        select id
          from public.articles
         where status='published' and category in ('reflection','trend')
         order by importance_score desc nulls last, published_at desc
         limit 1
      ),
      'discovery', (
        select id
          from public.articles
         where status='published' and category='discover'
         order by importance_score desc nulls last, published_at desc
         limit 1
      ),
      'wisdom_date', (
        select entry_date from public.wisdom_entries
         order by entry_date desc limit 1
      )
    )
  );
end;
$$;

revoke all on function internal.alam_refresh_intelligence() from public, anon, authenticated;

-- Populate the current state immediately on first application.
select internal.alam_refresh_intelligence();

-- Hourly maintenance at minute 07. Research/publication agents remain independent;
-- this job only refreshes deterministic derived state after their validated writes.
select cron.schedule(
  'alam-hourly-intelligence-refresh',
  '7 * * * *',
  $$select internal.alam_refresh_intelligence();$$
);
