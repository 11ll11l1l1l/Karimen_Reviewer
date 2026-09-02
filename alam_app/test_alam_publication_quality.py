"""Deterministic regression tests for ALAM trusted publication-quality preflight."""

from pathlib import Path

from alam_publication_quality import (
    PublicationQualityError,
    assess_article,
    persist_rejection,
    validate_archive_items,
)


def article(*, sources=None, claims=None, created_at="2026-09-03T05:00:00+09:00"):
    return {
        "id": "quality-story",
        "agent": "discover",
        "created_at": created_at,
        "type": "technology",
        "title": "Verified story",
        "summary": "What changed and why it matters.",
        "why_it_matters": "Useful consequence.",
        "importance": 70,
        "confidence": 80,
        "status": "NEW",
        "sources": sources if sources is not None else [
            {
                "publisher": "Official Agency",
                "title": "Primary notice",
                "url": "https://agency.example/notice",
                "source_type": "official",
            },
            {
                "publisher": "Independent News",
                "title": "Independent check",
                "url": "https://news.example/report",
                "source_type": "news",
            },
        ],
        "claims": claims if claims is not None else [
            {"kind": "FACT", "text": "The agency announced it.", "source_refs": [1]},
            {"kind": "INFERENCE", "text": "This may affect readers.", "source_refs": [1, 2]},
        ],
        "content": {},
    }


def assert_reason(record, expected):
    assessment = assess_article(record)
    assert not assessment["publishable"], assessment
    assert expected in assessment["reasons"], assessment


def test_valid_modern_record_passes():
    assessment = assess_article(article())
    assert assessment["publishable"], assessment
    assert assessment["reasons"] == []
    assert assessment["warnings"] == []
    assert assessment["metrics"]["source_count"] == 2
    assert assessment["metrics"]["primary_source_count"] == 1
    assert assessment["metrics"]["sourced_fact_count"] == 1


def test_no_sources_rejected():
    assert_reason(article(sources=[]), "no_sources")
    assert_reason(article(sources=[]), "no_usable_sources")


def test_malformed_source_url_rejected():
    bad = article(sources=[{"publisher": "Broken", "url": "not-a-url", "source_type": "news"}])
    assert_reason(bad, "source_1_invalid_url")
    assert_reason(bad, "no_usable_sources")


def test_fact_requires_source_ref():
    bad = article(claims=[{"kind": "FACT", "text": "Unsupported fact", "source_refs": []}])
    assert_reason(bad, "fact_1_missing_source_ref")


def test_any_supplied_ref_must_resolve():
    bad = article(claims=[{"kind": "INFERENCE", "text": "Bad mapping", "source_refs": [99]}])
    assert_reason(bad, "claim_1_source_ref_out_of_range")


def test_single_secondary_source_warns_but_does_not_block():
    one = article(
        sources=[{
            "publisher": "Newsroom",
            "title": "Only available report",
            "url": "https://news.example/only",
            "source_type": "news",
        }],
        # Keep every supplied reference valid so this test isolates the policy that
        # source-count/source-type concerns are warnings rather than publication blocks.
        claims=[
            {"kind": "FACT", "text": "The newsroom reported it.", "source_refs": [1]},
            {"kind": "INFERENCE", "text": "This may affect readers.", "source_refs": [1]},
        ],
    )
    assessment = assess_article(one)
    assert assessment["publishable"], assessment
    assert "single_source_only" in assessment["warnings"]
    assert "no_primary_or_official_source" in assessment["warnings"]


def test_legacy_record_without_sources_remains_rebuildable():
    legacy = article(sources=[], claims=[], created_at="2026-09-01T12:00:00+09:00")
    assessment = assess_article(legacy)
    assert assessment["publishable"], assessment
    assert assessment["reasons"] == []


def test_archive_quality_fails_before_database_layer():
    good = article()
    bad = article(sources=[])
    bad["id"] = "rejected-story"
    try:
        validate_archive_items([
            ("discover", Path("good.json"), good),
            ("discover", Path("bad.json"), bad),
        ])
    except PublicationQualityError as exc:
        assert len(exc.rejections) == 1
        rejection = exc.rejections[0]
        assert rejection["article_id"] == "rejected-story"
        assert "no_sources" in rejection["reasons"]
        assert rejection["path"] == "bad.json"
    else:
        raise AssertionError("unsafe archive should fail publication preflight")


class Response:
    def __init__(self, data=None):
        self.data = data or []


class RejectionQuery:
    def __init__(self, client):
        self.client = client
        self.action = None
        self.payload = None
        self.filters = []

    def select(self, _columns):
        self.action = "select"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = dict(payload)
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = dict(payload)
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        def matches(row):
            return all(row.get(column) == value for column, value in self.filters)

        if self.action == "select":
            rows = [row for row in self.client.rows if matches(row)]
            return Response([{"id": row["id"]} for row in rows[:1]])
        if self.action == "insert":
            row = dict(self.payload)
            row["id"] = f"rejection-{len(self.client.rows) + 1}"
            self.client.rows.append(row)
            return Response([row])
        if self.action == "update":
            for row in self.client.rows:
                if matches(row):
                    row.update(self.payload)
            return Response([])
        raise AssertionError(f"unexpected action {self.action}")


class RejectionClient:
    def __init__(self):
        self.rows = []

    def table(self, name):
        assert name == "rejected_candidates"
        return RejectionQuery(self)


def test_rejection_persistence_is_private_table_and_retry_idempotent():
    bad = article(sources=[])
    try:
        validate_archive_items([("discover", Path("bad.json"), bad)])
    except PublicationQualityError as exc:
        rejection = exc.rejections[0]
    else:
        raise AssertionError("expected publication rejection")

    client = RejectionClient()
    first_key = persist_rejection(client, rejection)
    second_key = persist_rejection(client, rejection)

    assert first_key == second_key
    assert len(client.rows) == 1
    row = client.rows[0]
    assert row["candidate_key"] == first_key
    assert row["reason"].startswith("publication_quality_gate:")
    assert row["quality_checks"]["blocking_reasons"]
    assert row["candidate"]["id"] == "quality-story"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"ALAM publication quality tests passed ({len(tests)})")
