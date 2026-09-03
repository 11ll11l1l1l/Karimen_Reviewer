-- Harden ALAM account identity/state Data API grants.
--
-- RLS protects rows, but PostgreSQL TRUNCATE is not subject to row-level security.
-- Earlier broad grants left authenticated with TRUNCATE/REFERENCES/TRIGGER and with
-- write privileges on account_visitor_links even though link writes are intentionally
-- mediated by SECURITY DEFINER RPCs. Keep only the table privileges the browser needs.
-- This migration is replay-safe and does not modify or delete product data.

alter table public.account_profiles enable row level security;
alter table public.account_visitor_links enable row level security;

-- Anonymous clients never access durable account identity tables directly.
revoke all privileges on table public.account_profiles from anon;
revoke all privileges on table public.account_visitor_links from anon;

-- Reset inherited/legacy broad grants, then explicitly allow only owner-scoped CRUD
-- supported by the existing account_profiles RLS policy.
revoke all privileges on table public.account_profiles from authenticated;
grant select, insert, update, delete on table public.account_profiles to authenticated;

-- Account/device links are read-only to authenticated browser clients. Linking is done
-- only through alam_link_current_account(), which validates auth.uid() and device state.
revoke all privileges on table public.account_visitor_links from authenticated;
grant select on table public.account_visitor_links to authenticated;
