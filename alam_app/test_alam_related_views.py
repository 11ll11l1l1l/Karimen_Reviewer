from alam_related_views import related_story_candidates, related_story_decision_preview, related_story_selection


def _story(story_id, tags, category="discover", importance=70):
    return {
        "id": story_id,
        "title": story_id,
        "tags": tags,
        "_category": category,
        "importance": importance,
        "confidence": 80,
        "created_at": "2026-09-03T10:00:00+09:00",
        "content": {},
    }


def test_related_stories_require_shared_validated_signal():
    base = _story("base", ["yen", "household"])
    linked = _story("linked", ["yen", "boj"], "reflection", 90)
    unrelated = _story("unrelated", ["semiconductor", "robot"], "discover", 99)
    rows = related_story_candidates(base, [base, unrelated, linked])
    assert [row[2]["id"] for row in rows] == ["linked"]
    assert rows[0][3] == ["yen"]


def test_explicit_connection_tags_work_without_title_inference():
    base = _story("base", [])
    base["content"] = {"connection_tags": ["rate-normalization"]}
    linked = _story("linked", [])
    linked["content"] = {"connection_tags": ["rate-normalization", "mortgages"]}
    rows = related_story_candidates(base, [base, linked])
    assert len(rows) == 1
    assert rows[0][3] == ["rate-normalization"]


def test_zero_and_one_story_states_are_safe():
    base = _story("base", ["yen"])
    assert related_story_candidates(base, []) == []
    assert related_story_candidates(base, [base]) == []


def test_concentrated_related_shelf_reserves_one_evidence_connected_different_lens():
    base = _story("base", ["yen", "household"])
    rows = [base]
    rows.extend(
        [
            _story("money-1", ["yen", "household"], "reflection", 99),
            _story("money-2", ["yen", "household"], "reflection", 95),
            _story("money-3", ["yen", "household"], "reflection", 90),
            _story("family-lens", ["yen"], "practical", 75),
        ]
    )
    selected, stretch_index = related_story_selection(base, rows, limit=3)
    assert [row[2]["id"] for row in selected[:2]] == ["money-1", "money-2"]
    assert selected[-1][2]["id"] == "family-lens"
    assert selected[-1][3] == ["yen"]
    assert stretch_index == 2


def test_already_diverse_related_shelf_keeps_original_ranking_without_stretch_attribution():
    base = _story("base", ["yen", "household"])
    rows = [
        base,
        _story("money", ["yen", "household"], "reflection", 99),
        _story("family", ["yen", "household"], "practical", 95),
        _story("discover", ["yen", "household"], "discover", 90),
        _story("extra", ["yen"], "trend", 80),
    ]
    selected, stretch_index = related_story_selection(base, rows, limit=3)
    assert [row[2]["id"] for row in selected] == ["money", "family", "discover"]
    assert stretch_index is None


def test_related_story_decision_preview_uses_only_explicit_reader_impact():
    record = _story("linked", ["yen"])
    record["why_it_matters"] = "  Household budgets may face higher imported-food costs.  "
    assert related_story_decision_preview(record) == "Household budgets may face higher imported-food costs."


def test_related_story_decision_preview_fails_closed_for_missing_structured_and_placeholder_values():
    record = _story("linked", ["yen"])
    assert related_story_decision_preview(record) == ""
    record["why_it_matters"] = {"generated": "Do this"}
    assert related_story_decision_preview(record) == ""
    record["why_it_matters"] = "TBD"
    assert related_story_decision_preview(record) == ""


def test_related_story_decision_preview_is_bounded_for_mobile_scanability():
    record = _story("linked", ["yen"])
    record["why_it_matters"] = "A" * 240
    preview = related_story_decision_preview(record, limit=80)
    assert len(preview) == 80
    assert preview.endswith("…")
