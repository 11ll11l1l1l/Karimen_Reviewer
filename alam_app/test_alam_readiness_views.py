"""Deterministic regression tests for ALAM's product-facing readiness presentation.

The backend classifier owns operational semantics. These tests protect the Product
layer from accidentally using reassuring copy for failure/fallback states or calling
sync age "story freshness", which would overstate what the telemetry proves.
"""

from alam_readiness import _readiness_product_copy, _sync_freshness_label


def test_ready_copy_is_explicitly_live():
    title, body = _readiness_product_copy("ready")
    assert "Live" in title
    assert "Supabase" in body


def test_fallback_copy_does_not_claim_database_live():
    title, body = _readiness_product_copy("local_fallback")
    combined = f"{title} {body}".lower()
    assert "fallback" in combined
    assert "instead of supabase" in combined


def test_stale_copy_describes_sync_not_article_truth():
    title, body = _readiness_product_copy("sync_stale")
    combined = f"{title} {body}".lower()
    assert "sync" in combined
    assert "not a claim" in combined
    assert "factually outdated" in combined


def test_failed_and_partial_states_are_not_softened():
    failed = " ".join(_readiness_product_copy("sync_failed")).lower()
    partial = " ".join(_readiness_product_copy("sync_partial")).lower()
    assert "failed" in failed
    assert "incomplete" in partial
    assert "fully healthy" in partial


def test_missing_rpc_has_specific_migration_language():
    title, body = _readiness_product_copy("sync_health_unavailable")
    assert "diagnostics" in title.lower()
    assert "function" in body.lower()


def test_sync_age_labels_are_compact_and_operational():
    assert _sync_freshness_label(None) is None
    assert _sync_freshness_label(0.01) == "Sync: just now"
    assert _sync_freshness_label(0.5) == "Sync: 30 min ago"
    assert _sync_freshness_label(2.25) == "Sync: 2.2 h ago"
    assert _sync_freshness_label(48) == "Sync: 2.0 d ago"


if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"{len(tests)} readiness-view tests passed")
