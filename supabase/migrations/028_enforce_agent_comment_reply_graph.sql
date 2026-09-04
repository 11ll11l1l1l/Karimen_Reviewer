-- ALAM migration 028: keep panel-comment reply graphs structurally valid.
-- Migration 013 prevents dangling reply_to values, but a foreign key alone still
-- permits self-replies, cross-article replies, and cycles created by later updates.
-- Those shapes break deterministic panel rendering/reconciliation and can make one
-- article's analytical thread point into another article. Enforce the graph at the
-- durable Supabase boundary so every trusted writer inherits the same invariant.

create or replace function public.alam_enforce_comment_reply_graph()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_parent_article_id uuid;
  v_cycle boolean := false;
begin
  -- Moving a parent comment to another article must not strand existing replies on
  -- the former article. The child rows themselves are not touched by that update, so
  -- validate the reverse edge here as well as NEW.reply_to below.
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
    -- The existing FK should also reject this, but failing here keeps the complete
    -- reply-graph contract in one place and produces a deterministic error.
    raise exception 'Reply parent does not exist.';
  end if;

  if v_parent_article_id is distinct from new.article_id then
    raise exception 'A reply and its parent must belong to the same article.';
  end if;

  -- UNION (not UNION ALL) also terminates safely if legacy corruption already formed
  -- a loop elsewhere in the ancestor chain. Any path that reaches NEW.id would make
  -- this write cyclic and must fail.
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

drop trigger if exists trg_alam_agent_comment_reply_graph on public.agent_comments;
create trigger trg_alam_agent_comment_reply_graph
before insert or update of reply_to, article_id
on public.agent_comments
for each row
execute function public.alam_enforce_comment_reply_graph();
