-- ALAM.ph least-privilege Data API grants.
-- RLS remains the row-level enforcement layer; grants limit reachable operations.

-- Shared intelligence: public clients may read only.
revoke all on table public.articles from anon, authenticated;
revoke all on table public.article_sources from anon, authenticated;
revoke all on table public.article_versions from anon, authenticated;
revoke all on table public.agent_comments from anon, authenticated;
revoke all on table public.topics from anon, authenticated;
revoke all on table public.article_topics from anon, authenticated;
revoke all on table public.predictions from anon, authenticated;
revoke all on table public.prediction_updates from anon, authenticated;
revoke all on table public.article_relationships from anon, authenticated;
revoke all on table public.media_assets from anon, authenticated;
revoke all on table public.wisdom_entries from anon, authenticated;
revoke all on table public.daily_briefings from anon, authenticated;
revoke all on table public.agents from anon, authenticated;

grant select on table public.articles to anon, authenticated;
grant select on table public.article_sources to anon, authenticated;
grant select on table public.article_versions to anon, authenticated;
grant select on table public.agent_comments to anon, authenticated;
grant select on table public.topics to anon, authenticated;
grant select on table public.article_topics to anon, authenticated;
grant select on table public.predictions to anon, authenticated;
grant select on table public.prediction_updates to anon, authenticated;
grant select on table public.article_relationships to anon, authenticated;
grant select on table public.media_assets to anon, authenticated;
grant select on table public.wisdom_entries to anon, authenticated;
grant select on table public.daily_briefings to anon, authenticated;
grant select on table public.agents to anon, authenticated;

-- Personal state: authenticated clients only; RLS scopes each row to its owner.
revoke all on table public.user_preferences from anon, authenticated;
revoke all on table public.saved_articles from anon, authenticated;
revoke all on table public.article_reads from anon, authenticated;
revoke all on table public.article_feedback from anon, authenticated;
revoke all on table public.notifications from anon, authenticated;

grant select, insert, update, delete on table public.user_preferences to authenticated;
grant select, insert, update, delete on table public.saved_articles to authenticated;
grant select, insert, update, delete on table public.article_reads to authenticated;
grant select, insert, update, delete on table public.article_feedback to authenticated;
grant select, update on table public.notifications to authenticated;

-- Analytics: anonymous is insert-only; authenticated readers may also read their own events.
revoke all on table public.app_events from anon, authenticated;
grant insert on table public.app_events to anon;
grant select, insert on table public.app_events to authenticated;
grant usage, select on sequence public.app_events_id_seq to anon, authenticated;
grant usage, select on sequence public.article_reads_id_seq to authenticated;

-- Internal/operator tables are never directly reachable by public clients.
revoke all on table public.agent_runs from anon, authenticated;
revoke all on table public.rejected_candidates from anon, authenticated;

-- Shared-content policies explicitly target Data API roles.
drop policy if exists "Public can read published articles" on public.articles;
create policy "Public can read published articles" on public.articles
for select to anon, authenticated using (status = 'published');

drop policy if exists "Public can read article sources" on public.article_sources;
create policy "Public can read article sources" on public.article_sources
for select to anon, authenticated using (
  exists (select 1 from public.articles a where a.id = article_sources.article_id and a.status = 'published')
);

drop policy if exists "Public can read published article versions" on public.article_versions;
create policy "Public can read published article versions" on public.article_versions
for select to anon, authenticated using (
  exists (select 1 from public.articles a where a.id = article_versions.article_id and a.status = 'published')
);

drop policy if exists "Public can read published comments" on public.agent_comments;
create policy "Public can read published comments" on public.agent_comments
for select to anon, authenticated using (status = 'published');

drop policy if exists "Public can read topics" on public.topics;
create policy "Public can read topics" on public.topics for select to anon, authenticated using (true);

drop policy if exists "Public can read article topics" on public.article_topics;
create policy "Public can read article topics" on public.article_topics for select to anon, authenticated using (true);

drop policy if exists "Public can read predictions" on public.predictions;
create policy "Public can read predictions" on public.predictions for select to anon, authenticated using (true);

drop policy if exists "Public can read prediction updates" on public.prediction_updates;
create policy "Public can read prediction updates" on public.prediction_updates for select to anon, authenticated using (true);

drop policy if exists "Public can read article relationships" on public.article_relationships;
create policy "Public can read article relationships" on public.article_relationships for select to anon, authenticated using (true);

drop policy if exists "Public can read media assets" on public.media_assets;
create policy "Public can read media assets" on public.media_assets
for select to anon, authenticated using (
  article_id is null or exists (select 1 from public.articles a where a.id = media_assets.article_id and a.status = 'published')
);

drop policy if exists "Public can read wisdom" on public.wisdom_entries;
create policy "Public can read wisdom" on public.wisdom_entries for select to anon, authenticated using (true);

-- Personal policies explicitly target authenticated users.
drop policy if exists "Users manage own preferences" on public.user_preferences;
create policy "Users manage own preferences" on public.user_preferences for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "Users manage own saved articles" on public.saved_articles;
create policy "Users manage own saved articles" on public.saved_articles for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "Users manage own reads" on public.article_reads;
create policy "Users manage own reads" on public.article_reads for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "Users manage own feedback" on public.article_feedback;
create policy "Users manage own feedback" on public.article_feedback for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "Users read own notifications" on public.notifications;
create policy "Users read own notifications" on public.notifications for select to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "Users update own notifications" on public.notifications;
create policy "Users update own notifications" on public.notifications for update to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

drop policy if exists "Users read own briefings" on public.daily_briefings;
drop policy if exists "Anon reads global briefings" on public.daily_briefings;
create policy "Anon reads global briefings" on public.daily_briefings for select to anon using (user_id is null);
create policy "Users read own briefings" on public.daily_briefings for select to authenticated
using (user_id is null or (select auth.uid()) = user_id);

drop policy if exists "Users insert own app events" on public.app_events;
drop policy if exists "Users read own app events" on public.app_events;
drop policy if exists "Anon inserts anonymous app events" on public.app_events;
create policy "Anon inserts anonymous app events" on public.app_events for insert to anon with check (user_id is null);
create policy "Users insert own app events" on public.app_events for insert to authenticated
with check (user_id is null or (select auth.uid()) = user_id);
create policy "Users read own app events" on public.app_events for select to authenticated
using ((select auth.uid()) = user_id);
