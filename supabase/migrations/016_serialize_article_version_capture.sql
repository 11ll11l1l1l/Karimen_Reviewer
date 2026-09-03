-- Prevent concurrent article updates from racing on MAX(version_no)+1.
--
-- The article-version trigger preserves immutable story history. Without a per-article
-- transaction lock, two concurrent writers can both compute the same next version number,
-- causing the UNIQUE(article_id, version_no) constraint to abort one synchronization path.
-- This migration keeps the existing semantics and serializes only writers for the same
-- article id; unrelated articles remain concurrent.

create or replace function internal.alam_capture_article_version()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
declare
  v_next integer;
begin
  if tg_op = 'UPDATE'
     and new.record is not distinct from old.record
     and new.lifecycle_status is not distinct from old.lifecycle_status then
    return new;
  end if;

  -- Serialize version-number allocation for this one article for the duration of the
  -- transaction. hashtextextended gives a deterministic bigint key suitable for the
  -- single-key advisory-lock API and avoids blocking updates to unrelated stories.
  perform pg_advisory_xact_lock(hashtextextended(new.id, 0));

  if exists (
    select 1
    from public.article_versions v
    where v.article_id = new.id
      and v.record = new.record
      and v.lifecycle_status is not distinct from new.lifecycle_status
  ) then
    return new;
  end if;

  select coalesce(max(v.version_no), 0) + 1
    into v_next
  from public.article_versions v
  where v.article_id = new.id;

  insert into public.article_versions (
    article_id,
    version_no,
    lifecycle_status,
    change_summary,
    record,
    created_at
  )
  values (
    new.id,
    v_next,
    new.lifecycle_status,
    case
      when tg_op = 'INSERT' then 'Automatic initial snapshot'
      else 'Automatic synchronized snapshot'
    end,
    new.record,
    coalesce(new.updated_at, new.created_at, now())
  );

  return new;
end;
$$;

revoke all on function internal.alam_capture_article_version() from public;
revoke all on function internal.alam_capture_article_version() from anon;
revoke all on function internal.alam_capture_article_version() from authenticated;
