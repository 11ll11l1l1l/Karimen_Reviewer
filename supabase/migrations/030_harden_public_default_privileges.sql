-- ALAM migration 030: fail closed for future application-owned objects in public.
-- Existing object grants and data are intentionally unchanged. Any future table,
-- sequence, or RPC created by ALAM migrations and meant to be browser-accessible
-- must opt in explicitly with a least-privilege GRANT (and RLS/policies for tables).
--
-- Supabase's migration runner owns ALAM-created objects as postgres. Platform-owned
-- supabase_admin default privileges are managed by Supabase and cannot be changed by
-- project migrations; do not attempt to mutate that provider-owned boundary here.

alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated;
