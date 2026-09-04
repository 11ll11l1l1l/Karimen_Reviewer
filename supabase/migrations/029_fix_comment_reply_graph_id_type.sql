-- ALAM migration 029: correct migration 028 for ALAM's text article IDs.
-- Migration 028 was applied with a uuid local variable even though
-- agent_comments.article_id is text. Preserve migration history and replace only the
-- trigger function with a schema-anchored %TYPE variable so future type changes also
-- remain compatible.

create or replace function public.alam_enforce_comment_reply_graph()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_parent_article_id public.agent_comments.article_id%type;
  v_cycle boolean := false;
begin
  if exists (
    select 1
    from public.agent_comments child
    where child.reply_to = new.id
      and child.article_id is distinct from new.article_id
  ) then
    raise exception 'Comment article_id cannot differ from an existing child reply.';
  end if;

  if new.reply_to is null then
    return new;
  end if;

  if new.reply_to = new.id then
    raise exception 'A comment cannot reply to itself.';
  end if;

  select parent.article_id
    into v_parent_article_id
  from public.agent_comments parent
  where parent.id = new.reply_to;

  if not found then
    raise exception 'Reply parent does not exist.';
  end if;

  if v_parent_article_id is distinct from new.article_id then
    raise exception 'A reply and its parent must belong to the same article.';
  end if;

  with recursive ancestors(id, reply_to) as (
    select parent.id, parent.reply_to
    from public.agent_comments parent
    where parent.id = new.reply_to
    union
    select parent.id, parent.reply_to
    from public.agent_comments parent
    join ancestors a on parent.id = a.reply_to
  )
  select exists(select 1 from ancestors where id = new.id)
    into v_cycle;

  if v_cycle then
    raise exception 'Comment reply graph cannot contain a cycle.';
  end if;

  return new;
end;
$$;

revoke all on function public.alam_enforce_comment_reply_graph() from public;
revoke all on function public.alam_enforce_comment_reply_graph() from anon, authenticated;
