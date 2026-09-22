"""Regression tests for ALAM trusted-sync fast-path planning."""
from alam_supabase_sync_job import _reconcile_plan_from_state

GOOD_TIME = "2026-09-22T00:00:00+00:00"

def test_healthy_previous_sync_uses_incremental_fast_path():
    reason, scope = _reconcile_plan_from_state("success", GOOD_TIME, [])
    assert reason is None and scope == []

def test_untracked_writes_reconcile_only_affected_articles():
    reason, scope = _reconcile_plan_from_state("success", GOOD_TIME, ["story-b", "story-a", "story-a"])
    assert "2 untracked public article" in reason
    assert scope == ["story-a", "story-b"]

def test_non_success_previous_sync_falls_back_to_full_repair():
    for status in ("failed", "partial", "running"):
        reason, scope = _reconcile_plan_from_state(status, GOOD_TIME, ["story-a"])
        assert status in reason and scope is None

def test_explicit_maintenance_forces_full_reconciliation():
    reason, scope = _reconcile_plan_from_state("success", GOOD_TIME, [], force_full=True)
    assert "explicit full reconciliation" in reason and scope is None

def test_missing_previous_sync_timestamp_fails_safe():
    reason, scope = _reconcile_plan_from_state("success", None, [])
    assert "timestamp is unavailable" in reason and scope is None
