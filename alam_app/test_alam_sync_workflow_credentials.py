from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "alam-supabase-sync.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_content_pushes_do_not_false_fail_on_missing_external_sync_credentials():
    text = _workflow_text()
    assert "id: supabase_credentials" in text
    assert 'echo "ready=$ready" >> "$GITHUB_OUTPUT"' in text
    assert "::warning::Missing repository Actions secret SUPABASE_URL" in text
    assert "::warning::Missing trusted Supabase backend credential" in text
    assert "if [[ \"${{ github.event_name }}\" == \"workflow_dispatch\" ]]" in text


def test_actual_supabase_sync_never_runs_without_trusted_credentials():
    text = _workflow_text()
    guard = "if: steps.supabase_credentials.outputs.ready == 'true'"
    assert text.count(guard) >= 2
    assert "Sync verified ALAM records to Supabase" in text
    assert "SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}" in text
    assert "SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}" in text


def test_manual_sync_request_still_fails_closed_when_credentials_are_missing():
    text = _workflow_text()
    assert "A manually requested Supabase sync cannot proceed without trusted credentials." in text
    assert "exit 1" in text
