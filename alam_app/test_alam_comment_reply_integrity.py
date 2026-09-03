"""Regression coverage for ALAM panel-comment reply integrity."""

from pathlib import Path

import validate_alam_data as validator


TEST_PATH = validator.ROOT / "data" / "comments" / "_reply_integrity_test.json"


def _comment(comment_id, story_id, created_at, reply_to=None):
    row = {
        "id": comment_id,
        "story_id": story_id,
        "created_at": created_at,
        "agent": "trend",
        "persona_id": "bea-base-rate",
        "body": "test",
    }
    if reply_to is not None:
        row["reply_to"] = reply_to
    return row


def _graph_errors(rows):
    original_rows = list(validator.COMMENT_ROWS)
    original_errors = list(validator.ERRORS)
    try:
        validator.COMMENT_ROWS[:] = [(TEST_PATH, row) for row in rows]
        validator.ERRORS.clear()
        validator.validate_comment_graph()
        return list(validator.ERRORS)
    finally:
        validator.COMMENT_ROWS[:] = original_rows
        validator.ERRORS[:] = original_errors


def test_valid_reply_graph_passes():
    rows = [
        _comment("parent", "story-a", "2026-09-03T10:00:00+09:00"),
        _comment("child", "story-a", "2026-09-03T10:01:00+09:00", "parent"),
    ]
    assert _graph_errors(rows) == []


def test_missing_reply_target_fails():
    errors = _graph_errors([
        _comment("child", "story-a", "2026-09-03T10:01:00+09:00", "missing"),
    ])
    assert any("does not exist in comment archive" in item for item in errors)


def test_cross_story_reply_fails():
    rows = [
        _comment("parent", "story-a", "2026-09-03T10:00:00+09:00"),
        _comment("child", "story-b", "2026-09-03T10:01:00+09:00", "parent"),
    ]
    errors = _graph_errors(rows)
    assert any("belongs to a different story" in item for item in errors)


def test_parent_must_precede_reply_for_deterministic_ingest():
    rows = [
        _comment("parent", "story-a", "2026-09-03T10:01:00+09:00"),
        _comment("child", "story-a", "2026-09-03T10:01:00+09:00", "parent"),
    ]
    errors = _graph_errors(rows)
    assert any("must be strictly older" in item for item in errors)


def test_migration_is_idempotent_and_non_destructive():
    migration = (
        validator.ROOT.parent / "supabase" / "migrations" / "013_agent_comment_reply_integrity.sql"
    ).read_text(encoding="utf-8")
    normalized = migration.lower()
    assert "if not exists idx_agent_comments_reply_to" in normalized
    assert "agent_comments_reply_to_fkey" in normalized
    assert "references public.agent_comments (id)" in normalized
    assert "on delete set null" in normalized
    assert "not valid" in normalized
    assert "validate constraint agent_comments_reply_to_fkey" in normalized
    for destructive in ("drop table", "truncate", "delete from public.agent_comments"):
        assert destructive not in normalized
