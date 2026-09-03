# ALAM optional account / Auth handoff — 2026-09-03

## Completed and verified

- Anonymous browser recognition remains the default and is not gated by account sign-in.
- `alam_auth.py` creates one Supabase Auth client per Streamlit session. It deliberately does not reuse the cached public read client and never requests a service-role credential.
- Settings now contains an explicit optional ALAM account section with email-code request, code verification, account status and sign-out controls. It is injected inside Settings so the compact mobile brand/Today shell and CookieManager layout invariants are unchanged.
- Repository migration `010_account_identity_bridge.sql` adds RLS-protected `account_profiles` and `account_visitor_links` plus authenticated-only RPC `alam_link_current_account(uuid)`.
- The migration was applied to live ALAM Project2 `zecztyabmmoqzjumhxxf` and verified: both tables exist; `anon` cannot execute the account-link RPC; `authenticated` can execute it. No Auth users existed at verification time, so no synthetic account was created.
- The link RPC is idempotent for the same user/device and refuses to link one anonymous visitor identity to two different Auth users. Existing anonymous rows are retained rather than reassigned or deleted.
- Existing authenticated state tables (`saved_articles`, `article_reads`, `article_feedback`, `user_preferences`) already use `auth.uid()` ownership policies, providing the target layer for later cross-device state migration.

## Current production status

The database/account-link foundation and Settings UI are deployed in repository main. Anonymous ALAM remains operational even when Auth is not configured or a user does not sign in. Account authentication is not yet declared end-to-end production-ready because the hosted Email Auth template is an external project setting and no real mailbox/Auth user was used during this automated iteration.

## Manual owner action / external blocker

In Supabase Project2, configure the Email/Magic Link template to deliver a six-digit OTP by including `{{ .Token }}` instead of relying only on `{{ .ConfirmationURL }}`. Supabase's passwordless email API sends a Magic Link by default; the OTP UI in ALAM requires the token template. Do not change ALAM to accept or log access tokens in query parameters as a workaround.

## Known risks and intentionally deferred work

- Auth session state is isolated correctly per Streamlit session, but durable restoration of a signed-in account across a brand-new Streamlit/browser session is not yet implemented. Anonymous device recognition remains durable independently.
- Account linking currently establishes ownership identity only. It does not yet copy/merge browser-local Saved/read/preferences/history into the existing `auth.uid()` state tables. That migration must be additive/idempotent and should be implemented only after a real OTP sign-in can be verified.
- `alam_link_current_account` is intentionally a `SECURITY DEFINER` RPC callable only by `authenticated`; the Supabase advisor therefore reports the expected signed-in SECURITY DEFINER warning. Its `search_path` is pinned, `auth.uid()` is required, anon execution is revoked, and device ownership conflicts are rejected.
- Existing anonymous identity RPCs still produce advisor warnings because they are intentionally callable before a user has an account. Abuse/rate limiting remains separate hardening work.

## Validation / next step

The ALAM Auth contract test checks session-client isolation, publishable-key-only usage, Settings placement, migration permissions and visitor-link uniqueness. The complete ALAM Actions gate includes data validation, existing regression tests, full `python -m compileall -q alam_app`, and Streamlit startup.

Next: after the Project2 email template is confirmed to emit `{{ .Token }}`, execute one real OTP sign-in through deployed ALAM, verify `auth.users`, `account_profiles` and `account_visitor_links`, verify sign-out/expiry behavior, then add idempotent migration/synchronization of Saved/read/preferences/history into their existing `auth.uid()` tables and durable Auth session restoration without weakening anonymous mode.
