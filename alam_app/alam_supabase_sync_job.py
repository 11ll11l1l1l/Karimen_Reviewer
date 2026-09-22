"""Observable, self-healing trusted Supabase synchronization job for ALAM.ph.

The low-level ingestion module intentionally focuses on incremental data mirroring.
This wrapper owns *operational* concerns: recording when a sync started, whether it
finished cleanly, which Git commit produced it, and the ingestion statistics emitted
by the underlying job. It also runs a deterministic reconciliation pass after normal
ingestion so a retry can repair an earlier partial write instead of preserving it.

This file must run only with a Supabase service-role/secret credential. It is never
imported by the public Streamlit app.
"""

from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

from alam_lifecycle import lifecycle_rejections
from alam_publication_quality import PublicationQualityError, persist_quality_rejections
from alam_supabase_ingest import _client, run as run_ingestion
from alam_supabase_reconcile import prepare_public_archive, reconcile_public_archive

SYNC_AGENT_ID = "alam_supabase_sync"
# Deliberately exceeds the workflow's 20-minute hard timeout; regression-enforced.
STALE_SYNC_RUN_MINUTES = 30
RECONCILE_DRIFT_TOLERANCE = timedelta(minutes=5)


def _utc_now():
    """Return an ISO-8601 UTC timestamp accepted by Supabase/Postgres."""
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value):
    """Normalize a database timestamp for synchronization planning."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _reconcile_plan_from_state(previous_status, previous_timestamp, drift_article_ids, force_full=False):
    """Return (reason, scope); scope=None means full reconciliation."""
    if force_full:
        return "explicit full reconciliation requested", None
    status = str(previous_status or "").strip().lower()
    if not status:
        return "no prior canonical synchronization is recorded", None
    if status != "success":
        return f"previous canonical synchronization status is {status}", None
    if _parse_utc(previous_timestamp) is None:
        return "previous canonical synchronization timestamp is unavailable", None
    ids = sorted({str(article_id) for article_id in (drift_article_ids or []) if article_id})
    if ids:
        return f"{len(ids)} untracked public article update(s) detected", ids
    return None, []


def _reconcile_plan(client):
    """Determine the smallest safe repair scope before creating the current run row."""
    force_full = os.environ.get("ALAM_FULL_RECONCILE", "").strip().lower() in {"1", "true", "yes", "on"}
    rows = (
        client.table("agent_runs")
        .select("status,started_at,finished_at")
        .eq("agent_id", SYNC_AGENT_ID)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return _reconcile_plan_from_state(None, None, [], force_full=force_full)
    previous = rows[0]
    previous_timestamp = previous.get("finished_at") or previous.get("started_at")
    base_reason, base_scope = _reconcile_plan_from_state(
        previous.get("status"), previous_timestamp, [], force_full=force_full
    )
    if base_reason:
        return base_reason, base_scope
    anchor = _parse_utc(previous_timestamp)
    cutoff = (anchor + RECONCILE_DRIFT_TOLERANCE).isoformat()
    drift_rows = (
        client.table("articles")
        .select("id,updated_at")
        .eq("status", "published")
        .gt("updated_at", cutoff)
        .order("updated_at")
        .limit(1000)
        .execute()
        .data
        or []
    )
    if len(drift_rows) >= 1000:
        return "large untracked public-write set requires full reconciliation", None
    return _reconcile_plan_from_state(
        previous.get("status"),
        previous_timestamp,
        [row.get("id") for row in drift_rows],
        force_full=False,
    )


def _workflow_metadata():
    """Capture deployment provenance without persisting secrets or environment dumps.

    GitHub exposes many environment variables to Actions. Only stable, non-secret
    identifiers are copied to the database so an operator can trace a failed sync to
    the exact commit/run without risking accidental credential disclosure.
    """
    keys = {
        "github_sha": "GITHUB_SHA",
        "github_ref": "GITHUB_REF",
        "github_run_id": "GITHUB_RUN_ID",
        "github_run_number": "GITHUB_RUN_NUMBER",
        "github_workflow": "GITHUB_WORKFLOW",
        "github_actor": "GITHUB_ACTOR",
    }
    return {label: os.environ.get(env_name) for label, env_name in keys.items() if os.environ.get(env_name)}


def _parse_stats(output):
    """Parse the final JSON statistics printed by ``alam_supabase_ingest.run``.

    The ingestion command currently writes one formatted JSON object to stdout.
    Parsing it here avoids coupling the trusted wrapper to internal counters while
    still allowing the run record to expose useful totals. If future diagnostic text
    is added before/after that object, failure to parse remains non-fatal: the sync's
    exit code is still authoritative and the raw console output is replayed to CI.
    """
    text = (output or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _story_counts(stats):
    """Translate trusted-sync counters into the generic ``agent_runs`` columns.

    ``article_rejected`` is populated by archive quality preflight before public
    mutation. Counting it separately from malformed low-level ``article_invalid``
    records keeps operator telemetry honest while preserving the existing run schema.
    """
    article_keys = [key for key in stats if key.startswith("article_") and not key.endswith("_errors")]
    found = sum(int(stats.get(key) or 0) for key in article_keys)
    published = int(stats.get("article_published") or 0)
    rejected = int(stats.get("article_invalid") or 0) + int(stats.get("article_rejected") or 0)
    return found, published, rejected


def _recover_stale_sync_runs(client):
    """Finalize only abandoned trusted-sync telemetry left by a killed runner.

    GitHub Actions gives the production sync job a 10-minute hard timeout. A hard
    timeout, cancellation, or runner loss can terminate Python before ``_finish_run``
    executes, leaving a durable ``running`` row forever. A later trusted sync can
    safely recover only this sync agent's rows once they are well beyond that runner
    window. Other agents and fresh sync runs are deliberately outside this update.
    """
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=STALE_SYNC_RUN_MINUTES)).isoformat()
    response = (
        client.table("agent_runs")
        .update({
            "finished_at": now.isoformat(),
            "status": "failed",
            "error_message": (
                "ALAM Supabase sync did not finalize before the runner safety window; "
                "recovered by a later trusted sync."
            ),
        })
        .eq("agent_id", SYNC_AGENT_ID)
        .eq("status", "running")
        .lt("started_at", cutoff)
        .execute()
    )
    return len(response.data or [])


def _insert_run(client):
    metadata = _workflow_metadata()
    metadata["job_kind"] = "github_json_to_supabase"
    response = client.table("agent_runs").insert({
        "agent_id": SYNC_AGENT_ID,
        "started_at": _utc_now(),
        "status": "running",
        "metadata": metadata,
    }).execute()
    rows = list(response.data or [])
    return rows[0].get("id") if rows else None


def _finish_run(client, run_id, exit_code, stats):
    if not run_id:
        return

    found, published, rejected = _story_counts(stats)
    error_count = sum(
        int(value or 0)
        for key, value in stats.items()
        if key.endswith("_errors")
    )

    # A run with some successful processing plus one or more isolated failures is
    # marked ``partial`` rather than ``failed``. This distinction is important for
    # overnight development: agents should repair the failed subset without assuming
    # that the entire Supabase mirror is unusable.
    if exit_code == 0:
        status = "success"
    elif found > 0 or published > 0:
        status = "partial"
    else:
        status = "failed"

    metadata = _workflow_metadata()
    metadata.update({
        "job_kind": "github_json_to_supabase",
        "ingestion_stats": stats,
        "error_count": error_count,
    })

    client.table("agent_runs").update({
        "finished_at": _utc_now(),
        "status": status,
        "stories_found": found,
        "stories_published": published,
        "stories_rejected": rejected,
        # Do not persist exception strings from third-party clients here because
        # they can occasionally include request details. CI logs retain the precise
        # diagnostics; the database stores only a safe operator-facing summary.
        "error_message": None if exit_code == 0 else "ALAM Supabase sync reported errors; inspect the matching GitHub Actions run.",
        "metadata": metadata,
    }).eq("id", run_id).execute()


def main():
    client = _client()
    run_id = None

    try:
        recovered_runs = _recover_stale_sync_runs(client)
        if recovered_runs:
            print(
                f"SYNC AUDIT: recovered {recovered_runs} stale {SYNC_AGENT_ID} run(s).",
                file=sys.stderr,
            )
    except Exception as exc:
        # Recovery is operational hygiene, not permission to block reconciliation.
        # A transient telemetry failure must not stop the trusted content mirror.
        print(f"SYNC AUDIT WARNING: could not recover stale {SYNC_AGENT_ID} runs: {exc}", file=sys.stderr)

    try:
        reconcile_reason, reconcile_scope = _reconcile_plan(client)
    except Exception as exc:
        reconcile_reason, reconcile_scope = "reconciliation health probe unavailable", None
        print(f"SYNC AUDIT WARNING: {exc}; falling back to full reconciliation.", file=sys.stderr)

    try:
        run_id = _insert_run(client)
    except Exception as exc:
        # Observability must never prevent the actual mirror from running. A missing
        #/outdated agent_runs table should be visible in CI, but ALAM's content sync
        # remains more important than telemetry during migrations or recovery.
        print(f"SYNC AUDIT WARNING: could not create agent_runs record: {exc}", file=sys.stderr)

    stats = {}
    prepared_archive = None

    # Validate the complete allow-listed public audit archive before incremental
    # ingestion. This single preflight covers evidence integrity, chronology ambiguity,
    # and lifecycle resurrection. A retired story may legitimately become active again,
    # but the audit record must say why; otherwise a stale agent retry could make an
    # already-settled item look newly actionable without any public-write rollback path.
    try:
        prepared_archive = prepare_public_archive()
        lifecycle_failures = lifecycle_rejections(prepared_archive)
        if lifecycle_failures:
            raise PublicationQualityError(lifecycle_failures)
        stats["archive_preflight_articles"] = len(prepared_archive)
    except PublicationQualityError as exc:
        stats["archive_preflight_errors"] = 1
        stats["article_rejected"] = len(exc.rejections)
        print(f"PUBLICATION QUALITY REJECTION: {exc}", file=sys.stderr)

        # Rejected payloads belong only in trusted diagnostics. The existing
        # rejected_candidates table is RLS-private with no anonymous read policy.
        # Persistence failure must never weaken the gate: the sync still exits before
        # any public article/source/version/topic mutation.
        try:
            stats["rejections_persisted"] = persist_quality_rejections(client, exc)
        except Exception as persist_exc:
            stats["rejection_persist_errors"] = 1
            print(
                f"REJECTION AUDIT WARNING: could not persist rejected candidate diagnostics: {persist_exc}",
                file=sys.stderr,
            )
        try:
            _finish_run(client, run_id, 1, stats)
        except Exception as audit_exc:
            print(f"SYNC AUDIT WARNING: could not finalize agent_runs record: {audit_exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        stats["archive_preflight_errors"] = 1
        print(f"ARCHIVE PREFLIGHT ERROR: {exc}", file=sys.stderr)
        try:
            _finish_run(client, run_id, 1, stats)
        except Exception as audit_exc:
            print(f"SYNC AUDIT WARNING: could not finalize agent_runs record: {audit_exc}", file=sys.stderr)
        raise SystemExit(1)

    captured = io.StringIO()
    try:
        with redirect_stdout(captured):
            exit_code = int(run_ingestion(dry_run=False))
    except Exception as exc:
        exit_code = 1
        print(f"SYNC FATAL ERROR: {exc}", file=sys.stderr)

    output = captured.getvalue()
    if output:
        # Replay ingestion statistics to Actions so existing operational behavior and
        # searchable logs are preserved despite capturing stdout for structured use.
        print(output, end="" if output.endswith("\n") else "\n")
    stats.update(_parse_stats(output))

    # Healthy content pushes use the incremental fast path. Full repair remains for
    # ingestion errors/maintenance; detected untracked writes repair only affected IDs.
    if exit_code != 0:
        reconcile_reason, reconcile_scope = "incremental ingestion reported errors", None

    if reconcile_reason:
        scope_count = len(prepared_archive) if reconcile_scope is None else len(reconcile_scope)
        stats["reconcile_scope_articles"] = scope_count
        print(f"ALAM reconciliation requested: {reconcile_reason} ({scope_count} article(s)).")
        try:
            reconcile_stats = reconcile_public_archive(
                client,
                prepared_archive=prepared_archive,
                article_ids=reconcile_scope,
            )
            stats.update(reconcile_stats)
            if reconcile_stats:
                print("ALAM reconciliation:")
                print(json.dumps(reconcile_stats, indent=2, ensure_ascii=False))
        except Exception as exc:
            stats["reconcile_errors"] = int(stats.get("reconcile_errors") or 0) + 1
            exit_code = 1
            print(f"RECONCILIATION ERROR: {exc}", file=sys.stderr)
    else:
        stats["reconcile_skipped_healthy"] = 1
        print("ALAM reconciliation skipped: canonical state is healthy and incremental ingestion completed cleanly.")

    try:
        _finish_run(client, run_id, exit_code, stats)
    except Exception as exc:
        print(f"SYNC AUDIT WARNING: could not finalize agent_runs record: {exc}", file=sys.stderr)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
