from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "alam-supabase-sync.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_sync_uses_public_project_url_as_non_secret_configuration():
    text = _workflow_text()
    assert "SUPABASE_URL: https://zecztyabmmoqzjumhxxf.supabase.co" in text
    assert "secrets.SUPABASE_URL" not in text


def test_every_sync_event_fails_closed_on_missing_trusted_backend_credential():
    text = _workflow_text()
    assert "Require trusted Supabase credential" in text
    assert "::error::Missing trusted Supabase backend credential" in text
    assert "Trusted Supabase credentials are required for every main-branch ALAM sync" in text
    assert "exit 1" in text
    assert "github.event_name" not in text
    assert "Supabase mirror skipped" not in text


def test_actual_supabase_sync_is_unconditional_after_required_credential_gate():
    text = _workflow_text()
    assert "Sync verified ALAM records to Supabase" in text
    assert "SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}" in text
    assert "SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}" in text
    assert "if: steps.supabase_credentials.outputs.ready == 'true'" not in text
    assert "id: supabase_credentials" not in text
    assert "if: steps.supabase-credential.outputs.available == 'true'" not in text


def test_canonical_sync_job_remains_the_only_workflow_database_writer():
    text = _workflow_text()
    assert "run: python alam_app/alam_supabase_sync_job.py" in text
    assert "alam_app/alam_supabase_ingest.py" in text
    assert "alam_app/alam_supabase_reconcile.py" in text
