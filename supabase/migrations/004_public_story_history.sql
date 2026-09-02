-- ALAM.ph read-only story-history access.
-- Historical versions are visible only when their parent story is published.

drop policy if exists "Public can read published article versions" on public.article_versions;
create policy "Public can read published article versions"
on public.article_versions for select using (
  exists (
    select 1 from public.articles a
    where a.id = article_id and a.status = 'published'
  )
);
