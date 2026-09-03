-- Keep public link-table visibility aligned with the publication boundary on articles.
--
-- `article_topics` and `article_relationships` are browser-readable query tables.
-- Their original SELECT policies used `USING (true)`, which could expose the IDs and
-- graph structure of future draft/rejected/internal article rows even though the
-- parent `articles` row itself is hidden by RLS.  Mirror the parent publication rule
-- here so every public graph edge is composed only of published articles.

alter table public.article_topics enable row level security;
alter table public.article_relationships enable row level security;

drop policy if exists "Public can read article topics" on public.article_topics;
create policy "Public can read article topics"
on public.article_topics
for select
to anon, authenticated
using (
    exists (
        select 1
        from public.articles as article
        where article.id = article_topics.article_id
          and article.status = 'published'
    )
);

drop policy if exists "Public can read article relationships" on public.article_relationships;
create policy "Public can read article relationships"
on public.article_relationships
for select
to anon, authenticated
using (
    exists (
        select 1
        from public.articles as source_article
        where source_article.id = article_relationships.from_article_id
          and source_article.status = 'published'
    )
    and exists (
        select 1
        from public.articles as target_article
        where target_article.id = article_relationships.to_article_id
          and target_article.status = 'published'
    )
);
