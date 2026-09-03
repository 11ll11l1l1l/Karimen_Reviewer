-- Keep browser-readable prediction data aligned with the publication boundary on articles.
--
-- `predictions` and `prediction_updates` are exposed query tables. Their original
-- SELECT policies used `USING (true)`, which could expose prediction claims or update
-- history attached to future draft/rejected/internal articles even while the parent
-- article itself remains hidden by RLS. Mirror the parent publication rule here.

alter table public.predictions enable row level security;
alter table public.prediction_updates enable row level security;

drop policy if exists "Public can read predictions" on public.predictions;
create policy "Public can read predictions"
on public.predictions
for select
to anon, authenticated
using (
    exists (
        select 1
        from public.articles as article
        where article.id = predictions.article_id
          and article.status = 'published'
    )
);

drop policy if exists "Public can read prediction updates" on public.prediction_updates;
create policy "Public can read prediction updates"
on public.prediction_updates
for select
to anon, authenticated
using (
    exists (
        select 1
        from public.predictions as prediction
        join public.articles as article
          on article.id = prediction.article_id
        where prediction.id = prediction_updates.prediction_id
          and article.status = 'published'
    )
);
