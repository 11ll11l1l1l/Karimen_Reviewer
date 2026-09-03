-- Optional Supabase Auth account foundation for ALAM.ph.
-- Anonymous browsing remains fully supported. This migration only adds a durable
-- account profile and an authenticated bridge from the existing random browser
-- device identity to auth.users. It never reassigns or deletes anonymous history.

create table if not exists public.account_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '',
  primary_visitor_id uuid null references public.visitor_profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.account_visitor_links (
  user_id uuid not null references auth.users(id) on delete cascade,
  visitor_id uuid not null references public.visitor_profiles(id) on delete cascade,
  linked_at timestamptz not null default now(),
  primary key (user_id, visitor_id),
  unique (visitor_id)
);

alter table public.account_profiles enable row level security;
alter table public.account_visitor_links enable row level security;

drop policy if exists "Users manage own account profile" on public.account_profiles;
create policy "Users manage own account profile"
on public.account_profiles
for all
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "Users read own visitor links" on public.account_visitor_links;
create policy "Users read own visitor links"
on public.account_visitor_links
for select
to authenticated
using ((select auth.uid()) = user_id);

revoke all on public.account_profiles from anon;
revoke all on public.account_visitor_links from anon;
grant select, insert, update, delete on public.account_profiles to authenticated;
grant select on public.account_visitor_links to authenticated;

create or replace function public.alam_link_current_account(p_device_id uuid)
returns table (
  user_id uuid,
  visitor_id uuid,
  display_name text,
  linked_at timestamptz
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_user uuid := auth.uid();
  v_visitor uuid;
  v_name text;
  v_existing_user uuid;
begin
  if v_user is null then
    raise exception 'authentication_required';
  end if;

  select d.visitor_id, p.display_name
    into v_visitor, v_name
  from public.visitor_devices d
  join public.visitor_profiles p on p.id = d.visitor_id
  where d.device_id = p_device_id;

  if v_visitor is null then
    raise exception 'unrecognized_device';
  end if;

  select l.user_id into v_existing_user
  from public.account_visitor_links l
  where l.visitor_id = v_visitor;

  if v_existing_user is not null and v_existing_user <> v_user then
    raise exception 'device_already_linked';
  end if;

  insert into public.account_profiles(user_id, display_name, primary_visitor_id)
  values (v_user, coalesce(v_name, ''), v_visitor)
  on conflict (user_id) do update
    set display_name = case
          when public.account_profiles.display_name = '' then excluded.display_name
          else public.account_profiles.display_name
        end,
        primary_visitor_id = coalesce(public.account_profiles.primary_visitor_id, excluded.primary_visitor_id),
        updated_at = now();

  insert into public.account_visitor_links(user_id, visitor_id)
  values (v_user, v_visitor)
  on conflict (user_id, visitor_id) do nothing;

  return query
  select l.user_id, l.visitor_id, p.display_name, l.linked_at
  from public.account_visitor_links l
  join public.visitor_profiles p on p.id = l.visitor_id
  where l.user_id = v_user and l.visitor_id = v_visitor;
end;
$$;

revoke all on function public.alam_link_current_account(uuid) from public;
revoke all on function public.alam_link_current_account(uuid) from anon;
grant execute on function public.alam_link_current_account(uuid) to authenticated;
