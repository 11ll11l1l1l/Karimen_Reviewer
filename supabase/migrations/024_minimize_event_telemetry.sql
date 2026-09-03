-- ALAM.ph privacy-minimized telemetry boundary.
-- Browser telemetry is intentionally narrow: keep the stable event taxonomy and only
-- retain the small, non-PII property set that the product currently uses.
-- Unknown properties are dropped rather than persisted so analytics cannot become an
-- accidental arbitrary-data ingestion channel. Existing events are not modified.

create or replace function public.alam_log_event(
  p_device_id uuid,
  p_session_id text,
  p_event_name text,
  p_article_id text default null,
  p_properties jsonb default '{}'::jsonb
)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_visitor uuid;
  v_event_id bigint;
  v_article text;
  v_properties jsonb := '{}'::jsonb;
begin
  if p_event_name is null or p_event_name !~ '^[a-z][a-z0-9_]{0,63}$' then
    raise exception 'Invalid event name.';
  end if;
  if p_event_name not in (
    'app_open',
    'article_open',
    'navigation',
    'onboarding_completed',
    'ui_control_changed'
  ) then
    raise exception 'Unsupported event name.';
  end if;
  if p_session_id is not null and char_length(p_session_id) > 120 then
    raise exception 'Session identifier is too long.';
  end if;
  if p_properties is null then
    p_properties := '{}'::jsonb;
  end if;
  if jsonb_typeof(p_properties) <> 'object' then
    raise exception 'Event properties must be a JSON object.';
  end if;
  if octet_length(p_properties::text) > 8192 then
    raise exception 'Event properties are too large.';
  end if;

  -- Event-specific allowlists prevent arbitrary browser text/PII from being retained.
  if p_event_name = 'app_open' then
    v_properties := p_properties & array['recognized_device'];
  elsif p_event_name = 'article_open' then
    v_properties := p_properties & array['category', 'type'];
  elsif p_event_name = 'navigation' then
    v_properties := p_properties & array['page', 'section'];
  elsif p_event_name = 'onboarding_completed' then
    v_properties := p_properties & array['returning_device'];
  elsif p_event_name = 'ui_control_changed' then
    v_properties := p_properties & array['control', 'value'];
  end if;

  -- Only small scalar values are useful for ALAM aggregate analytics. Drop any
  -- nested/oversized values instead of storing opaque client payloads.
  select coalesce(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
    into v_properties
    from jsonb_each(v_properties) as e(key, value)
   where jsonb_typeof(e.value) in ('string', 'number', 'boolean', 'null')
     and octet_length(e.value::text) <= 160;

  select d.visitor_id into v_visitor
    from public.visitor_devices d
   where d.device_id = p_device_id;

  if v_visitor is null then
    raise exception 'Unknown ALAM device.';
  end if;

  -- Preserve referential integrity without leaking arbitrary article existence.
  -- Telemetry can associate only with a public/published article.
  if p_article_id is not null and exists (
    select 1
      from public.articles a
     where a.id = p_article_id
       and a.status = 'published'
  ) then
    v_article := p_article_id;
  else
    v_article := null;
  end if;

  insert into public.app_events(
    visitor_id, device_id, session_id, event_name, article_id, properties
  ) values (
    v_visitor, p_device_id, p_session_id, p_event_name, v_article, v_properties
  ) returning id into v_event_id;

  update public.visitor_devices
     set last_seen_at = now(), last_session_id = p_session_id
   where device_id = p_device_id;

  update public.visitor_profiles
     set last_seen_at = now(), interaction_count = interaction_count + 1
   where id = v_visitor;

  return v_event_id;
end;
$$;

revoke all on function public.alam_log_event(uuid,text,text,text,jsonb) from public;
grant execute on function public.alam_log_event(uuid,text,text,text,jsonb) to anon, authenticated;
