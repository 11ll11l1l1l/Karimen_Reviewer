import sys
from types import SimpleNamespace

import alam_runtime_safety as runtime_safety


def test_personalization_score_guard_normalizes_v5_scores_without_mutating_record():
    calls = {}

    def legacy_personal_relevance(record):
        calls["personal"] = record
        return float(record.get("importance", 50))

    def legacy_story_lifecycle(record, all_records):
        calls["lifecycle"] = record
        return "CONFIRMED" if float(record.get("confidence", 0)) >= 80 else "DEVELOPING"

    fake_intelligence = SimpleNamespace(
        personal_relevance=legacy_personal_relevance,
        story_lifecycle=legacy_story_lifecycle,
    )
    prior = sys.modules.get("alam_intelligence")
    sys.modules["alam_intelligence"] = fake_intelligence
    try:
        runtime_safety._install_intelligence_score_guard()
        # Installing twice must not stack wrappers across Streamlit reruns.
        runtime_safety._install_intelligence_score_guard()

        record = {
            "id": "score-shape-regression",
            "importance": {"score": "92"},
            "confidence": "HIGH",
        }
        original = dict(record)

        assert fake_intelligence.personal_relevance(record) == 92.0
        assert fake_intelligence.story_lifecycle(record, [record]) == "CONFIRMED"
        assert calls["personal"]["importance"] == 92.0
        assert calls["lifecycle"]["confidence"] == 80.0
        assert record == original
    finally:
        if prior is None:
            sys.modules.pop("alam_intelligence", None)
        else:
            sys.modules["alam_intelligence"] = prior


def test_personalization_score_guard_uses_safe_defaults_for_malformed_scores():
    normalized = runtime_safety._normalize_intelligence_scores(
        {"importance": {"unexpected": "shape"}, "confidence": "not-a-score"}
    )

    assert normalized["importance"] == 50.0
    assert normalized["confidence"] == 0.0
