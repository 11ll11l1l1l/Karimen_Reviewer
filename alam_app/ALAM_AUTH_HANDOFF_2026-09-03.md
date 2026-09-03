# ALAM optional account / Auth handoff — 2026-09-03

## Completed and verified

- Anonymous browser recognition remains the default and is not gated by account sign-in.
- `alam_auth.py` creates one Supabase Auth client per Streamlit session. It deliberately does not reuse the cached public read client and never requests a service-role credential.
- Settings contains an explicit optional ALAM account section with email-code request, code verification, account status, manual account-state sync and sign-out controls. It is injected inside Settings so the compact mobile brand/Today shell and CookieManager layout invariants are unchanged.
- A verified Supabase access/refresh token pair is persisted only in the top-level browser origin's localStorage and restored with `auth.set_session()`. Rotated refresh credentials are persisted again after successful restore; invalid/revoked sessions fail closed and clear stored credentials.
- Repository migration `010_account_identity_bridge.sql` adds RLS-protected `account_profiles` and `account_visitor_links` plus authenticated-only RPC `alam_link_current_account(uuid)`.
- Repository migration `011_index_account_primary_visitor.sql` adds the index required by the account profile's primary visitor relationship.
- Repository migration `012_account_state_history_bridge.sql` adds nullable `article_reads.source_event_id`, an idempotency index, and authenticated-only RPC `alam_import_current_device_reads(uuid)` so linked anonymous article-open telemetry can be preserved in account read history without deleting or rewriting the original audit events.
- Migrations 010–012 are applied to live ALAM Project2 `zecztyabmmoqzjumhxxf`. The current read-history importer permission boundary was verified directly: `anon` cannot execute it and `authenticated` can.
- The account state merge is additive. Valid browser Saved article IDs are unioned with cloud Saved rows. Existing cloud preferences win over a fresh browser; browser preferences are imported only when the account has no preference row. Linked anonymous article-open events are imported idempotently into `article_reads`.
- Invalid/stale browser Saved IDs are not pushed through the account foreign key. They remain local instead of causing the complete sync to fail or being silently deleted.
- Existing anonymous read/mute/feedback/saved-version profile data is never broadly reset during account hydration. Cloud preference restoration updates only the preference/settings portion of the portable profile.
- The identity link remains idempotent for the same user/device and refuses to link one anonymous visitor identity to two different Auth users. Existing anonymous rows are retained rather than reassigned or deleted.

## Current production status

The account identity, browser-session restoration and first authenticated cross-device state bridge are deployed in repository main. Anonymous ALAM remains operational when Auth is unused, unavailable or not configured. Signed-in Settings now provides visible account-state status for Saved count, account read-history count and whether preferences were restored from the account or imported from this browser.

Project2 was still at 0 Auth users, 0 account profiles and 0 account links at the start of this iteration. Therefore the schema and application behavior can be validated without converting or risking existing account state, but real email OTP sign-in is still not declared end-to-end production verified.

## Manual owner action / external blocker

In Supabase Project2, configure the Email/Magic Link template to deliver a six-digit OTP by including `{{ .Token }}` instead of relying only on `{{ .ConfirmationURL }}`. The ALAM UI expects the six-digit token. Do not change ALAM to accept or log access tokens in query parameters as a workaround.

After changing that template, execute one real mailbox sign-in through deployed ALAM and verify the resulting `auth.users`, `account_profiles`, `account_visitor_links`, `saved_articles`, `user_preferences` and imported `article_reads` rows under the authenticated user's RLS session.

## Known risks and intentionally deferred work

- Account state currently synchronizes during the Settings account flow rather than on every Saved/read/preference mutation. This is deliberately conservative while real OTP login remains externally unverified. The next product step after the first real login should make signed-in Saved/read/preference mutations write through immediately while preserving browser-local fallback on failure.
- Local mute and ranking-feedback signals remain browser-local. They are hashed compact profile state and should not be guessed/reconstructed into account rows without a trustworthy article-ID mapping.
- Cloud-restored Saved IDs are active in the signed-in Streamlit session. They are not forcibly written back into the anonymous Saved cookie because signing out should not unexpectedly rewrite browser-only state merely because another account was opened.
- `alam_link_current_account` and `alam_import_current_device_reads` are intentionally `SECURITY DEFINER` RPCs callable only by `authenticated`; their `search_path` is pinned and anonymous execution is revoked.
- Existing anonymous identity RPCs remain callable before sign-in by design. Abuse/rate limiting remains separate hardening work.

## Validation / next step

The ALAM Auth contract regression now covers session-client isolation, publishable-key-only usage, browser session restoration, fail-closed sign-out, bounded/deduplicated Saved-ID import, non-destructive cloud preference hydration, authenticated state-table usage and the migration 012 read-history idempotency/permission contract. The ALAM Actions gate also includes production-data validation, full `python -m compileall -q alam_app`, existing regressions and Streamlit startup.

Next: confirm the Project2 Email template emits `{{ .Token }}`, perform one real deployed OTP login, verify the RLS-backed state rows end-to-end, then promote Saved/read/preference synchronization from Settings-time merge to immediate write-through for signed-in readers while retaining anonymous/browser-local fallback.
