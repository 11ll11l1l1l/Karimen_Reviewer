-- ALAM anonymous visitor identity + interaction telemetry.
-- Public Streamlit never receives trusted write credentials. The publishable client
-- may call only the narrow SECURITY DEFINER RPCs below; direct visitor/event table
-- writes remain blocked by RLS.

create table if not exists public.visitor_profiles (
  id uuid primary key default gen_random_uuid(),
  display_name text not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  interaction_count bigint not null default 0,
  preferences jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  constraint visitor_profiles_display_name_len
    check (char_length(btrim(display_name)) between 1 and 80)
);

create table if not exists public.visitor_devices (
  device_id uuid primary key,
  visitor_id uuid not null references public.visitor_profiles(id) on delete cascade,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_session_id text,
  metadata jsonb not null default '{}'::jsonb,
  constraint visitor_devices_session_len
    check (last_session_id is null or char_length(last_session_id) <= 120)
);

create index if not exists visitor_devices_visitor_idx
  on public.visitor_devices(visitor_id);

alter table public.app_events
  add column if not exists visitor_id uuid references public.visitor_profiles(id) on delete set null,
  add column if not exists device_id uuid references public.visitor_devices(device_id) on delete set null;

create index if not exists app_events_visitor_created_idx
  on public.app_events(visitor_id, created_at desc);
create index if not exists app_events_device_created_idx
  on public.app_events(device_id, created_at desc);

alter table public.visitor_profiles enable row level security;
alter table public.visitor_devices enable row level security;

-- Keep direct public access closed. Identity is available only through validated RPCs.
revoke all on table public.visitor_profiles from anon, authenticated;
revoke all on table public.visitor_devices from anon, authenticated;

create or replace function public.alam_lookup_device(p_device_id uuid)
returns table (
  visitor_id uuid,
  display_name text,
  last_seen_at timestamptz,
  interaction_count bigint
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  update public.visitor_devices
     set last_seen_at = now()
   where device_id = p_device_id;

  update public.visitor_profiles p
     set last_seen_at = now()
    from public.visitor_devices d
   where d.device_id = p_device_id
     and p.id = d.visitor_id;

  return query
  select p.id, p.display_name, p.last_seen_at, p.interaction_count
    from public.visitor_profiles p
    join public.visitor_devices d on d.visitor_id = p.id
   where d.device_id = p_device_id
   limit 1;
end;
$$;

create or replace function public.alam_register_device(
  p_device_id uuid,
  p_display_name text,
  p_session_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns table (
  visitor_id uuid,
  display_name text,
  created_at timestamptz
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_name text := btrim(coalesce(p_display_name, ''));
  v_visitor uuid;
  v_created timestamptz;
begin
  if char_length(v_name) < 1 or char_length(v_name) > 80 then
    raise exception 'Display name must be between 1 and 80 characters.';
  end if;
  if p_session_id is not null and char_length(p_session_id) > 120 then
    raise exception 'Session identifier is too long.';
  end if;
  if octet_length(coalesce(p_metadata, '{}'::jsonb)::text) > 4096 then
    raise exception 'Metadata is too large.';
  end if;

  select d.visitor_id into v_visitor
    from public.visitor_devices d
   where d.device_id = p_device_id;

  if v_visitor is null then
    insert into public.visitor_profiles(display_name, metadata)
    values (v_name, coalesce(p_metadata, '{}'::jsonb))
    returning id, public.visitor_profiles.created_at into v_visitor, v_created;

    insert into public.visitor_devices(device_id, visitor_id, last_session_id, metadata)
    values (p_device_id, v_visitor, p_session_id, coalesce(p_metadata, '{}'::jsonb));
  else
    update public.visitor_devices
       set last_seen_at = now(),
           last_session_id = coalesce(p_session_id, last_session_id)
     where device_id = p_device_id;

    update public.visitor_profiles
       set last_seen_at = now()
     where id = v_visitor
     returning public.visitor_profiles.created_at into v_created;
  end if;

  return query
  select p.id, p.display_name, p.created_at
    from public.visitor_profiles p
   where p.id = v_visitor;
end;
$$;

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
set search_path = public, pg_temp
as $$
declare
  v_visitor uuid;
  v_event_id bigint;
  v_article text;
begin
  if p_event_name is null or p_event_name !~ '^[a-z][a-z0-9_]{0,63}$' then
    raise exception 'Invalid event name.';
  end if;
  if p_session_id is not null and char_length(p_session_id) > 120 then
    raise exception 'Session identifier is too long.';
  end if;
  if octet_length(coalesce(p_properties, '{}'::jsonb)::text) > 8192 then
    raise exception 'Event properties are too large.';
  end if;

  select d.visitor_id into v_visitor
    from public.visitor_devices d
   where d.device_id = p_device_id;

  if v_visitor is null then
    raise exception 'Unknown ALAM device.';
  end if;

  -- Preserve referential integrity without leaking whether an arbitrary article ID
  -- exists through an error path. Unknown/stale IDs are logged as non-article events.
  if p_article_id is not null and exists (
    select 1 from public.articles a where a.id = p_article_id
  ) then
    v_article := p_article_id;
  else
    v_article := null;
  end if;

  insert into public.app_events(
    visitor_id, device_id, session_id, event_name, article_id, properties
  ) values (
    v_visitor, p_device_id, p_session_id, p_event_name, v_article,
    coalesce(p_properties, '{}'::jsonb)
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

revoke all on function public.alam_lookup_device(uuid) from public;
revoke all on function public.alam_register_device(uuid,text,text,jsonb) from public;
revoke all on function public.alam_log_event(uuid,text,text,text,jsonb) from public;

grant execute on function public.alam_lookup_device(uuid) to anon, authenticated;
grant execute on function public.alam_register_device(uuid,text,text,jsonb) to anon, authenticated;
grant execute on function public.alam_log_event(uuid,text,text,text,jsonb) to anon, authenticated;
