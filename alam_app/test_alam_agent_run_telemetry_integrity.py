"""Regression guard for durable agent_runs telemetry invariants."""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "031_enforce_agent_run_telemetry_integrity.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_agent_run_counts_cannot_be_negative() -> None:
    sql = _sql()
    assert "agent_runs_nonnegative_counts_check" in sql
    assert "stories_found >= 0" in sql
    assert "stories_published >= 0" in sql
    assert "stories_rejected >= 0" in sql


def test_agent_run_timestamps_remain_ordered() -> None:
    sql = _sql()
    assert "agent_runs_time_order_check" in sql
    assert "finished_at is null or finished_at >= started_at" in sql


def test_agent_run_status_and_completion_timestamp_are_atomic_contract() -> None:
    sql = _sql()
    assert "agent_runs_lifecycle_check" in sql
    assert "status = 'running' and finished_at is null" in sql
    assert "status in ('success', 'partial', 'failed') and finished_at is not null" in sql


def test_agent_run_constraints_are_replay_safe() -> None:
    sql = _sql()
    for name in (
        "agent_runs_nonnegative_counts_check",
        "agent_runs_time_order_check",
        "agent_runs_lifecycle_check",
    ):
        assert f"conname = '{name}'" in sql
