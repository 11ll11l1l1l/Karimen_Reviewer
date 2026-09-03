# ALAM Saved Collections handoff — 2026-09-03

## User problem

Saved had become a useful material-change review queue, but every bookmark still lived in one flat list. The live account table already had a `collection` column, yet the product hard-coded account imports to `saved` and exposed no organization UI.

## Decision

Add six intentionally small collections: Read Later, Important, Money, Japan, Family, and Ideas. Keep anonymous ALAM fully functional by persisting collection assignments in a bounded browser cookie keyed by a short hash of the stable story ID. When an authenticated session is already active, read and write the existing `saved_articles.collection` field using the per-session Supabase client and normal RLS. No service-role path and no schema migration are required.

## Implementation

- Saved now shows collection counts and an `All`/collection filter.
- Every saved card has a collection selector.
- Existing database value `saved` is treated as backward-compatible `Read Later`.
- Anonymous assignments persist for one year in a bounded cookie; raw story IDs are not duplicated into that collection cookie.
- Signed-in collection changes upsert only the current user's saved row through the existing authenticated client/RLS policy.
- If cloud collection access fails, Saved remains usable and explicitly falls back to browser organization.
- Existing update badges, Before/Now preview, review acknowledgement, and Saved ID import/export remain intact.

## Live Supabase verification before implementation

Project `zecztyabmmoqzjumhxxf` has `saved_articles(user_id, article_id, collection, created_at)`. The table's active policy is `Users manage own saved articles`, role `authenticated`, with both `USING` and `WITH CHECK` constrained to `auth.uid() = user_id`. At this checkpoint the project had 31 article rows and zero Auth users/saved rows, so no user data migration was necessary and no synthetic user was created.

## Validation

The Saved regression suite now covers collection normalization, compatibility with legacy `saved`, malformed-cookie fallback, and hashed cookie keys in addition to existing material-update behavior. `alam_saved_views.py` and the regression file were syntax-parsed before commit. The ALAM Actions workflow remains the authoritative post-push gate for production data validation, the Saved regression, full `python -m compileall -q alam_app`, and Streamlit startup.

## Remaining limitation / next step

Account collection mirroring can only be exercised end-to-end after the externally blocked email OTP setup produces a real authenticated user. Until then anonymous collection organization is fully usable. A later account-state pass should import pre-existing anonymous non-default collection assignments during first account synchronization rather than waiting for the user to touch each collection after sign-in.
