-- Preserve anonymous ALAM article-open history when a browser is linked to an Auth account.
-- The source event id makes the migration idempotent across reruns, restored sessions,
-- and multiple Settings visits. Existing anonymous events remain untouched as audit data.

alter table public.article_reads
  add column if not exists source_event_id bigint references public.app_events(id) on delete set null;

create unique index if not exists article_reads_source_event_id_idx
  on public.article_reads (source_event_id)
  where source_event_id is not null;

create or replace function public.alam_import_current_device_reads(p_device_id uuid)
returns table(imported_reads bigint, total_account_reads bigint)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_visitor uuid;
  v_imported bigint := 0;
begin
  if v_user is null then
    raise exception 'Authentication required';
  end if;

  select d.visitor_id
    into v_visitor
  from public.visitor_devices d
  where d.device_id = p_device_id
  limit 1;

  if v_visitor is null then
    raise exception 'Unknown ALAM device';
  end if;

  -- Never infer ownership from the device alone. The identity bridge must already
  -- have linked this visitor to the authenticated account, and visitor_id is unique
  -- across accounts by the account_visitor_links constraint.
  if not exists (
    select 1
    from public.account_visitor_links l
    where l.user_id = v_user
      and l.visitor_id = v_visitor
  ) then
    raise exception 'ALAM device is not linked to this account';
  end if;

  insert into public.article_reads (
    user_id,
    article_id,
    opened_at,
    source_event_id
  )
  select
    v_user,
    e.article_id,
    e.created_at,
    e.id
  from public.app_events e
  join public.articles a on a.id = e.article_id
  where e.visitor_id = v_visitor
    and e.event_name = 'article_open'
    and e.article_id is not null
  on conflict do nothing;

  get diagnostics v_imported = row_count;

  return query
  select
    v_imported,
    count(*)::bigint
  from public.article_reads r
  where r.user_id = v_user;
end;
$$;

revoke all on function public.alam_import_current_device_reads(uuid) from public;
revoke all on function public.alam_import_current_device_reads(uuid) from anon;
grant execute on function public.alam_import_current_device_reads(uuid) to authenticated;
