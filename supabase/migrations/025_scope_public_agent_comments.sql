-- ALAM.ph public comment graph boundary.
-- A published analytical comment is public only while its parent article is public.
-- This prevents a comment status from leaking draft/internal article existence or analysis.
-- Existing rows are not modified; this only narrows browser-visible SELECT rows.

drop policy if exists "Public can read published comments" on public.agent_comments;

create policy "Public can read published comments"
on public.agent_comments
for select
to anon, authenticated
using (
  status = 'published'
  and exists (
    select 1
    from public.articles article
    where article.id = agent_comments.article_id
      and article.status = 'published'
  )
);
