"""Regression tests for ALAM's reader-facing evidence calculations.

These tests intentionally exercise only deterministic helpers. Rendering remains a
Streamlit smoke-test responsibility, while these assertions protect the semantics
behind the metrics shown to readers.
"""

from alam_evidence_views import evidence_summary, source_claim_map


def test_evidence_summary_counts_primary_groups_and_claim_coverage():
    record = {
        "sources": [
            {
                "publisher": "Ministry A",
                "url": "https://agency.example.jp/release/1",
                "source_type": "official",
            },
            {
                "publisher": "News B",
                "url": "https://news.example.com/story",
                "source_type": "news",
            },
            {
                # Same publisher as source 2: multiple links must not inflate the
                # source-diversity heuristic.
                "publisher": "News B",
                "url": "https://news.example.com/followup",
                "source_type": "news",
            },
        ],
        "claims": [
            {"kind": "FACT", "text": "Official measure announced.", "source_refs": [1]},
            {"kind": "INFERENCE", "text": "Likely household impact.", "source_refs": [1, 2]},
            {"kind": "ESTIMATE", "text": "Estimated cost effect.", "source_refs": []},
        ],
    }

    metrics = evidence_summary(record)
    assert metrics["source_count"] == 3
    assert metrics["primary_count"] == 1
    assert metrics["distinct_groups"] == 2
    assert metrics["claim_count"] == 3
    assert metrics["covered_claims"] == 2
    assert metrics["claim_coverage"] == 67
    assert metrics["referenced_sources"] == 2


def test_source_claim_map_ignores_invalid_references():
    record = {
        "sources": [
            {"publisher": "A", "url": "https://a.example", "source_type": "official"},
            {"publisher": "B", "url": "https://b.example", "source_type": "research"},
        ],
        "claims": [
            {"kind": "FACT", "text": "One", "source_refs": [1, 1, 99, "bad"]},
            {"kind": "FACT", "text": "Two", "source_refs": "2"},
            {"kind": "OPINION", "text": "Three"},
        ],
    }

    mapping = source_claim_map(record)
    assert [item[0] for item in mapping[1]] == [1]
    assert [item[0] for item in mapping[2]] == [2]
    assert set(mapping) == {1, 2}


def test_empty_evidence_is_explicit_not_fake_precision():
    metrics = evidence_summary({"sources": [], "claims": []})
    assert metrics == {
        "source_count": 0,
        "primary_count": 0,
        "distinct_groups": 0,
        "claim_count": 0,
        "covered_claims": 0,
        "claim_coverage": None,
        "referenced_sources": 0,
    }


if __name__ == "__main__":
    test_evidence_summary_counts_primary_groups_and_claim_coverage()
    test_source_claim_map_ignores_invalid_references()
    test_empty_evidence_is_explicit_not_fake_precision()
    print("ALAM evidence-view regression tests passed")
