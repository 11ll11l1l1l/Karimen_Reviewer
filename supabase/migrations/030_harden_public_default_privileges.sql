-- ALAM migration 030: fail closed for future browser-facing objects in public.
-- Existing object grants and data are intentionally unchanged. Any future table,
-- sequence, or RPC that is meant to be browser-accessible must opt in explicitly
-- with a least-privilege GRANT (and RLS/policies for tables).

alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated;

-- Supabase-managed migrations can also create public objects as supabase_admin.
-- Harden that owner as well so a change in migration execution role cannot silently
-- restore broad browser defaults.
alter default privileges for role supabase_admin in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role supabase_admin in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role supabase_admin in schema public
  revoke execute on functions from public, anon, authenticated;
