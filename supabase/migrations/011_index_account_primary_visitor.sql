-- Cover the account_profiles.primary_visitor_id foreign key used by the
-- anonymous-device -> authenticated-account identity bridge.
-- Safe to re-run and does not modify existing identity data.

create index if not exists account_profiles_primary_visitor_id_idx
  on public.account_profiles (primary_visitor_id);
