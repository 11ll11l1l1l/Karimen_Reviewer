"""Regression guard for ALAM's trusted Supabase sync workflow boundary."""

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "alam-supabase-sync.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_every_sync_event_fails_closed_without_trusted_credential():
    text = _workflow_text()
    assert "Require trusted Supabase credential" in text
    assert 'if [[ -z "$SUPABASE_SERVICE_ROLE_KEY" && -z "$SUPABASE_SECRET_KEY" ]]; then' in text
    assert "::error::Missing trusted Supabase backend credential" in text
    assert "exit 1" in text
    assert "EVENT_NAME:" not in text
    assert "available=false" not in text
    assert "exit 0" not in text


def test_database_write_step_occurs_after_stale_snapshot_and_credential_gates():
    text = _workflow_text()
    stale = text.index("- name: Reject stale main snapshot")
    gate = text.index("- name: Require trusted Supabase credential")
    install = text.index("- name: Install Supabase client")
    sync = text.index("- name: Sync verified ALAM records to Supabase")
    assert stale < gate < install < sync
    assert "run: python alam_app/alam_supabase_sync_job.py" in text
    assert "SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}" in text
    assert "SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}" in text


def test_stale_rerun_cannot_reconcile_older_archive_into_supabase():
    text = _workflow_text()
    assert "fetch-depth: 0" in text
    assert "git fetch --no-tags origin main" in text
    assert 'CURRENT_MAIN="$(git rev-parse origin/main)"' in text
    assert 'if [[ "$GITHUB_SHA" != "$CURRENT_MAIN" ]]; then' in text
    assert "::error::Refusing stale ALAM sync" in text
    assert "newer main commit exists" in text.lower()
    assert "exit 1" in text


def test_sync_is_pinned_to_alam_project():
    text = _workflow_text()
    assert "SUPABASE_URL: https://zecztyabmmoqzjumhxxf.supabase.co" in text
    assert "zkfmgezvzugchcwppreq" not in text
