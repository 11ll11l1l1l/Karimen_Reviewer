"""Regression guards for abandoned trusted-sync telemetry recovery."""

from pathlib import Path
import re

APP_DIR = Path(__file__).resolve().parent
SYNC_SOURCE = (APP_DIR / "alam_supabase_sync_job.py").read_text(encoding="utf-8")
WORKFLOW_SOURCE = (APP_DIR.parent / ".github" / "workflows" / "alam-supabase-sync.yml").read_text(encoding="utf-8")


def _function_block(name, next_name):
    start = SYNC_SOURCE.index(f"def {name}")
    end = SYNC_SOURCE.index(f"def {next_name}", start)
    return SYNC_SOURCE[start:end]


def test_stale_sync_recovery_is_scoped_and_conservative():
    timeout_match = re.search(r"timeout-minutes:\s*(\d+)", WORKFLOW_SOURCE)
    recovery_match = re.search(r"STALE_SYNC_RUN_MINUTES\s*=\s*(\d+)", SYNC_SOURCE)
    assert timeout_match is not None
    assert recovery_match is not None

    workflow_timeout = int(timeout_match.group(1))
    recovery_window = int(recovery_match.group(1))
    assert recovery_window > workflow_timeout

    recovery = _function_block("_recover_stale_sync_runs(client):", "_insert_run(client):")
    assert '.eq("agent_id", SYNC_AGENT_ID)' in recovery
    assert '.eq("status", "running")' in recovery
    assert '.lt("started_at", cutoff)' in recovery
    assert '"status": "failed"' in recovery
    assert '"finished_at": now.isoformat()' in recovery


def test_recovery_runs_before_new_sync_telemetry_insert():
    main = SYNC_SOURCE[SYNC_SOURCE.index("def main():"):]
    recovery_call = main.index("_recover_stale_sync_runs(client)")
    insert_call = main.index("_insert_run(client)")
    assert recovery_call < insert_call
    assert "could not recover stale" in main


if __name__ == "__main__":
    test_stale_sync_recovery_is_scoped_and_conservative()
    test_recovery_runs_before_new_sync_telemetry_insert()
    print("ALAM stale sync-run recovery regression test passed")
