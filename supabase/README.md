# ALAM.ph Supabase activation

ALAM keeps GitHub JSON as the agent/audit trail and uses Supabase as the durable query/read/state layer.

## 1. Run the database migrations

Open Supabase -> SQL Editor.

### Existing ALAM Supabase project created with the earlier UUID schema

The first ALAM Supabase schema used UUID article IDs. The v5 agent/audit contract uses stable text article IDs, so do not alter those UUID IDs in place.

Run these files in order:

1. `supabase/ALAM_EXISTING_DB_PATCH.sql`
2. `supabase/ALAM_FULL_SETUP.sql`

The compatibility bridge is non-destructive. It preserves the earlier UUID tables as `*_legacy_20260902` and leaves the existing `agents` table intact. PostgreSQL keeps the old foreign-key relationships attached to those preserved tables.

### Fresh ALAM Supabase project

Run `supabase/ALAM_FULL_SETUP.sql`.

The individual migration files remain available for development/history:

1. `supabase/migrations/001_alam_core.sql`
2. `supabase/migrations/003_comments_and_wisdom.sql`
3. `supabase/migrations/004_public_story_history.sql`

If an earlier draft of `001_alam_core.sql` was already executed before the lifecycle/status correction, use `002_alam_schema_corrections.sql` before migrations 003 and 004.

Do not put the service-role/secret key in Streamlit Secrets or public code.

## 2. Add GitHub Actions secrets

Repository -> Settings -> Secrets and variables -> Actions -> New repository secret.

Required:

- `SUPABASE_URL` = the same Supabase project URL used by Streamlit
- `SUPABASE_SERVICE_ROLE_KEY` = the project's server-side service-role/secret key

The public Streamlit deployment continues to use only:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`

## 3. Initial data sync

In GitHub -> Actions -> `ALAM Supabase sync` -> Run workflow.

The workflow validates ALAM JSON before any database write. It then mirrors verified articles, sources, story versions, tags, cross-agent comments, wisdom entries and prediction records to Supabase.

Future commits under the ALAM data directories trigger the sync automatically.

## 4. Verify cutover

Open ALAM -> More -> Settings.

Expected after at least one real article has synced:

- Supabase connected
- Live article feed: Supabase
- Database counts visible for articles, sources, comments, predictions and wisdom

Until Supabase contains a published article, ALAM intentionally keeps the local JSON migration fallback so production does not go blank.

## Security model

- Anonymous/public clients: read published shared intelligence only.
- Authenticated users: their own preference/saved/read/feedback state only when account support is enabled.
- Agent ingestion: GitHub Actions server-side service role only.
- No public client may insert/update/delete shared ALAM content.
- Job Radar remains private and is never ingested into the public ALAM application.
