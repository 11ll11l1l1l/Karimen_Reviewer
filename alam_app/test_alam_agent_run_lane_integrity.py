"""Regression guard for stability-agent telemetry lane serialization."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "034_enforce_single_running_stability_lane.sql"


def test_stability_agent_aliases_share_one_running_slot() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    normalized = " ".join(sql.split()).lower()

    assert "create unique index if not exists agent_runs_one_running_stability_lane_idx" in normalized
    assert "on public.agent_runs ((1))" in normalized
    assert "status = 'running'" in normalized
    assert "'stability_integration'" in normalized
    assert "'stability_integration_agent'" in normalized
    assert "agent_id in" in normalized


def test_stability_lane_guard_does_not_rewrite_history() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "update public.agent_runs" not in sql
    assert "delete from public.agent_runs" not in sql
    assert "drop index" not in sql
