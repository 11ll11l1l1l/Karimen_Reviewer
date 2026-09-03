-- Anonymous identity is a browser continuity primitive, not a fingerprinting store.
-- The public RPC must therefore ignore arbitrary client JSON (including User-Agent,
-- IP-like strings, or future accidental payloads) and persist only the two bounded
-- non-identifying implementation labels ALAM currently needs.
create or replace function public.alam_register_device(
  p_device_id uuid,
  p_display_name text,
  p_session_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns table(visitor_id uuid, display_name text, created_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_name text := btrim(coalesce(p_display_name, ''));
  v_visitor uuid;
  v_created timestamptz;
  v_metadata jsonb := jsonb_strip_nulls(jsonb_build_object(
    'identity_model', case when jsonb_typeof(p_metadata -> 'identity_model') = 'string' then left(p_metadata ->> 'identity_model', 64) end,
    'app', case when jsonb_typeof(p_metadata -> 'app') = 'string' then left(p_metadata ->> 'app', 64) end
  ));
begin
  if char_length(v_name) < 1 or char_length(v_name) > 80 then
    raise exception 'Display name must be between 1 and 80 characters.';
  end if;
  if p_session_id is not null and char_length(p_session_id) > 120 then
    raise exception 'Session identifier is too long.';
  end if;

  select d.visitor_id into v_visitor
  from public.visitor_devices d
  where d.device_id = p_device_id;

  if v_visitor is null then
    insert into public.visitor_profiles(display_name, metadata)
    values (v_name, v_metadata)
    returning id, public.visitor_profiles.created_at into v_visitor, v_created;

    insert into public.visitor_devices(device_id, visitor_id, last_session_id, metadata)
    values (p_device_id, v_visitor, p_session_id, v_metadata);
  else
    update public.visitor_devices
    set last_seen_at = now(), last_session_id = coalesce(p_session_id, last_session_id)
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

revoke all on function public.alam_register_device(uuid, text, text, jsonb) from public;
grant execute on function public.alam_register_device(uuid, text, text, jsonb) to anon, authenticated;
