-- ALAM.ph durable story identity guard.
-- A non-null story_key represents one continuing story across updates. Allowing two
-- article rows to share it can split future versions, sources, comments and sync state
-- across competing durable identities. The live dataset is checked before rollout and
-- currently contains no duplicate non-null story keys.
--
-- The partial unique index preserves NULL for records that legitimately do not yet
-- participate in story-key reconciliation. CREATE INDEX IF NOT EXISTS makes replay safe.

create unique index if not exists articles_story_key_unique_idx
  on public.articles (story_key)
  where story_key is not null;
