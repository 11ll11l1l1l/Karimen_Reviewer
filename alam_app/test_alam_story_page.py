"""Regression coverage for article-detail compatibility and grounded action context."""

from alam_story_page import _practical_action_snapshot, _practical_action_tradeoffs, _score_value


def test_article_detail_accepts_v5_semantic_and_nested_scores():
    assert _score_value("HIGH") == 80.0
    assert _score_value({"score": "92"}) == 92.0
    assert _score_value("88.5%") == 88.5


def test_article_detail_score_normalization_is_bounded_and_safe():
    assert _score_value(150) == 100.0
    assert _score_value(-10) == 0.0
    assert _score_value({"unknown": "shape"}, 50.0) == 50.0
    assert _score_value("not scored", 50.0) == 50.0


def test_practical_action_snapshot_uses_only_explicit_validated_fields():
    record = {
        "id": "practical-1",
        "_category": "practical",
        "content": {
            "who_is_affected": "  Families   with children  ",
            "deadline": "September 30, 2026",
            "risk_if_ignored": "Miss the filing window.",
        },
    }
    assert _practical_action_snapshot(record) == [
        ("Affected", "Families with children"),
        ("Deadline / timing", "September 30, 2026"),
        ("If ignored", "Miss the filing window."),
    ]


def test_practical_action_snapshot_fails_closed_for_missing_or_malformed_metadata():
    assert _practical_action_snapshot({"_category": "discover", "content": {"deadline": "Tomorrow"}}) == []
    record = {
        "_category": "practical",
        "content": {
            "who_is_affected": {"group": "families"},
            "deadline": "TBD",
            "when": ["September"],
            "risk_if_ignored": True,
        },
    }
    assert _practical_action_snapshot(record) == []


def test_practical_action_tradeoffs_show_only_explicit_article_metadata():
    record = {
        "_category": "practical",
        "content": {
            "potential_benefit": "  Save up to ¥20,000  ",
            "downside": "Requires an in-person visit.",
            "effort": "About 30 minutes",
            "financial_impact": "LOW",
        },
    }
    assert _practical_action_tradeoffs(record) == [
        ("Potential benefit", "Save up to ¥20,000"),
        ("Downside", "Requires an in-person visit."),
        ("Effort / cost", "About 30 minutes"),
    ]


def test_practical_action_tradeoffs_fail_closed_and_use_financial_fallback_when_effort_missing():
    assert _practical_action_tradeoffs({"_category": "discover", "content": {"effort": "LOW"}}) == []
    malformed = {
        "_category": "practical",
        "content": {"potential_benefit": ["saving"], "downside": "unknown", "effort": "TBD"},
    }
    assert _practical_action_tradeoffs(malformed) == []
    fallback = {"_category": "practical", "content": {"financial_impact": "MED"}}
    assert _practical_action_tradeoffs(fallback) == [("Effort / cost", "MED")]