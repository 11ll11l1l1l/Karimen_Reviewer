"""Regression coverage for article-detail score compatibility."""

from alam_story_page import _score_value


def test_article_detail_accepts_v5_semantic_and_nested_scores():
    assert _score_value("HIGH") == 80.0
    assert _score_value({"score": "92"}) == 92.0
    assert _score_value("88.5%") == 88.5


def test_article_detail_score_normalization_is_bounded_and_safe():
    assert _score_value(150) == 100.0
    assert _score_value(-10) == 0.0
    assert _score_value({"unknown": "shape"}, 50.0) == 50.0
    assert _score_value("not scored", 50.0) == 50.0
