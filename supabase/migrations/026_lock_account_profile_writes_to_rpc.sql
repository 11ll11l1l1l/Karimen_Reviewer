-- ALAM migration 026: keep durable account/profile identity writes behind trusted RPCs.
--
-- Row-level security limits which account_profiles row an authenticated user can reach,
-- but it does not restrict which columns that user can mutate. In particular,
-- primary_visitor_id is an identity-bridge field maintained by alam_link_current_account()
-- together with account_visitor_links. Direct Data API writes could otherwise create a
-- profile/link mismatch by changing or deleting the profile independently of that RPC.
--
-- Current browser code does not write account_profiles directly. Preserve owner-scoped
-- SELECT for diagnostics/account UI, and require all mutations to flow through the
-- authenticated SECURITY DEFINER bridge. This migration is replay-safe and changes no data.

alter table public.account_profiles enable row level security;

revoke insert, update, delete on table public.account_profiles from authenticated;
grant select on table public.account_profiles to authenticated;

-- Keep anonymous clients completely outside durable account identity state.
revoke all privileges on table public.account_profiles from anon;
