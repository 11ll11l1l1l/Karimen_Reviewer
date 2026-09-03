"""Regression guard for ALAM's trusted Supabase sync workflow boundary."""

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "alam-supabase-sync.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_normal_push_does_not_false_red_when_trusted_credentials_are_missing():
    text = _workflow_text()
    assert 'EVENT_NAME: ${{ github.event_name }}' in text
    assert 'if [[ "$EVENT_NAME" == "workflow_dispatch" ]]' in text
    assert 'echo "available=false" >> "$GITHUB_OUTPUT"' in text
    assert 'echo "::warning::Trusted Supabase backend credential is not configured' in text


def test_manual_sync_still_fails_closed_without_credentials():
    text = _workflow_text()
    manual_guard = text.index('if [[ "$EVENT_NAME" == "workflow_dispatch" ]]')
    fail_closed = text.index("exit 1", manual_guard)
    normal_skip = text.index("exit 0", fail_closed)
    assert manual_guard < fail_closed < normal_skip


def test_database_write_steps_cannot_run_without_a_trusted_credential():
    text = _workflow_text()
    gate = "if: steps.supabase-credential.outputs.available == 'true'"
    assert text.count(gate) >= 2
    assert "run: python alam_app/alam_supabase_sync_job.py" in text
    assert "SUPABASE_URL: https://zecztyabmmoqzjumhxxf.supabase.co" in text
    assert "zkfmgezvzugchcwppreq" not in text
