# ALAM Innovation handoff — grounded recovery after incomplete action outcome

## User problem

The new action-outcome reflection could learn that a validated checklist only partly worked or did not solve the reader's need, but the product then stopped. A reader who explicitly said they still needed help had no immediate safe continuation path.

## Root cause

Action follow-through and Ask ALAM were separate product surfaces. The completion reflection recorded a bounded usefulness outcome but did not connect an unresolved outcome to the existing evidence-only retrieval experience.

## Decision

For `partly` and `no` outcomes only, offer one optional **Ask ALAM about this** continuation. Prefill Ask ALAM from the validated story title, falling back to the validated action-plan goal. Never collect or infer a reason for failure, never generate new advice inside the checklist, and preserve Ask ALAM's existing insufficient-evidence refusal.

## Implementation

- `alam_action_checklist.py` adds deterministic `recovery_query()` and `open_grounded_recovery()` helpers.
- After an outcome of `partly` or `no`, article detail explains that Ask ALAM will use the current story topic and can answer only from validated ALAM records.
- The full-width recovery button clears the selected-story route, opens `More > Ask ALAM`, and preloads the grounded retrieval query.
- A `yes` outcome does not show the continuation, avoiding needless engagement prompts after the user's need was solved.
- If neither a validated story title nor action-plan goal exists, the feature fails closed and shows no recovery CTA.
- No free-text outcome reason, new telemetry field, article content, schema, migration, RLS, Auth, or service-role change was introduced.

## Mobile behavior

The continuation is one full-width button directly beneath the recorded unresolved outcome, preserving the existing touch-target contract and avoiding another dense control group.

## Validation

`test_alam_action_outcome.py` now covers title-first query construction, goal fallback, no-topic fail-closed behavior, exact route transition to the existing Ask ALAM surface, and preservation of the earlier bounded outcome/telemetry contract.

Pre-change `main` was `f862f90036f46df08cae021abd7b4f5f2a97cdf1`; its latest repository CI run was successful before this iteration. Post-change GitHub Actions must be read from the workflow attached to the final handoff revision.

## Live Supabase observation

A fresh aggregate query against the required project `zecztyabmmoqzjumhxxf` was attempted but blocked by the connector safety layer. No production counts are invented. There was no evidence that the external Auth blocker changed, so it was not revisited.

## Remaining limitation

Ask ALAM retrieval is deterministic lexical retrieval over the validated corpus. The recovery path can surface only what ALAM already has evidence for; when the archive has no supporting record, the existing explicit insufficient-evidence state remains the correct result.

## Recommended next Innovation step

Improve the recovery answer itself only if it can distinguish already-completed checklist instructions from genuinely additional validated evidence. Do not respond to a `no` outcome by simply repeating the same plan as if it were new help.
