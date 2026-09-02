from alam_runtime_safety import EXPECTED_SUPABASE_PROJECT_REF, _is_expected_supabase_url


def test_accepts_only_alam_project2_host():
    correct = f"https://{EXPECTED_SUPABASE_PROJECT_REF}.supabase.co"
    assert _is_expected_supabase_url(correct)
    assert _is_expected_supabase_url(correct + "/")
    assert not _is_expected_supabase_url("https://zkfmgezvzugchcwppreq.supabase.co")
    assert not _is_expected_supabase_url("https://example.com")
    assert not _is_expected_supabase_url("")
