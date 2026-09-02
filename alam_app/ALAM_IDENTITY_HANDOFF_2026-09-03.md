# ALAM identity / personalization handoff — 2026-09-03

This is a focused roadmap addendum for the anonymous visitor-identity production change. It should be folded into `ALAM_CONTINUOUS_ROADMAP.md` during the next roadmap consolidation pass.

## Completed and verified

- Added migration `006_anonymous_visitor_identity.sql` and applied it to the only live ALAM Supabase project, Project2 `zecztyabmmoqzjumhxxf`.
- Added RLS-protected `visitor_profiles` and `visitor_devices`; direct anon/auth table access is revoked.
- Added random-cookie device identity. ALAM explicitly does **not** fingerprint hardware/browser attributes and does not store IP addresses for recognition.
- Added narrow public RPCs for device lookup, first registration and interaction logging. RPC input sizes/names are validated and unknown article IDs are safely logged without an article FK.
- Extended `app_events` with nullable `visitor_id` and `device_id` foreign keys plus lookup indexes.
- Added first-visit welcome/onboarding before article-feed hydration, with a dedicated ALAM welcome illustration and name collection.
- Returning recognized devices receive a personalized welcome.
- Added app-open, navigation, article-open and safe structured-control telemetry for future personalization. Free text is deliberately excluded from automatic widget telemetry.
- Production RPC behavior was tested inside a transaction and rolled back; post-test counts confirmed zero synthetic profiles/devices/events remained.
- Main CI passed after onboarding integration, including the existing Streamlit startup gate.

## Security / privacy decisions

- Public Streamlit still uses only the publishable Supabase key.
- Visitor/event writes happen only through constrained SECURITY DEFINER RPCs; tables remain RLS-protected.
- Supabase's linter intentionally reports anonymous SECURITY DEFINER RPC warnings because these three functions are deliberately public onboarding endpoints. Their scope is narrow and input-limited. Reassess abuse/rate-limiting if ALAM becomes publicly high-traffic.
- `visitor_profiles`/`visitor_devices` intentionally have RLS enabled with no direct policies (deny-by-default). The linter reports this as informational.
- Device recognition uses a 128-bit random UUID cookie, not a derived fingerprint.

## Production state

- Migration `anonymous_visitor_identity` is present in Project2 migration history.
- Project2 remained healthy during the change.
- Existing article/comment/wisdom content was not modified or deleted.

## Remaining limitations / next steps

1. Measure real onboarding completion and RPC error rates before expanding telemetry.
2. Add explicit user-facing rename/reset/forget-this-device controls.
3. Move current browser-local Saved/preferences/read baselines into visitor-scoped Supabase state only after a narrow RLS/RPC design; preserve local fallback.
4. Add server-side abuse controls/rate limiting before broad public launch if registration/event volume becomes untrusted at scale.
5. Fold this addendum into the shared continuous roadmap after the current concurrent edit window closes.
