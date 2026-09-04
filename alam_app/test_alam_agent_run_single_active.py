"""Regression guard for the single-active-run agent coordination invariant."""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "033_enforce_single_running_agent_run.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_agent_run_uniqueness_is_scoped_only_to_running_rows() -> None:
    sql = _sql()
    assert "create unique index if not exists agent_runs_one_running_per_agent_idx" in sql
    assert "on public.agent_runs (agent_id)" in sql
    assert "where status = 'running'" in sql


def test_completed_agent_run_history_is_not_constrained() -> None:
    sql = _sql()
    assert "status in ('success', 'partial', 'failed')" not in sql
    assert "delete from public.agent_runs" not in sql
    assert "truncate" not in sql
