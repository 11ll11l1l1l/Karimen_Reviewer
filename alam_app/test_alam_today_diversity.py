"""Regression tests for Today anti-filter-bubble discovery insertion."""
import alam_today_page as today


def _record(record_id, category, relevance, shared):
    return {"id": record_id, "_category": category, "relevance": relevance, "shared": shared}


def _with_test_ranking(callback):
    old_rank, old_feed = today._rank, today.feed_score
    today._rank = lambda record: (record["relevance"], record["shared"])
    today.feed_score = lambda record: record["shared"]
    try:
        callback()
    finally:
        today._rank, today.feed_score = old_rank, old_feed


def test_concentrated_personalized_shelf_reserves_one_outside_category():
    def run():
        records = [_record(f"p{i}", "practical", 100-i, 50-i) for i in range(6)]
        records += [_record("trend-stretch", "trend", 20, 99), _record("discover-stretch", "discover", 10, 80)]
        chosen, stretch = today._discover_pool(records, set(), limit=6)
        assert len(chosen) == 6
        assert stretch is not None
        assert stretch["id"] == "trend-stretch"
        assert chosen[-1]["id"] == "trend-stretch"
        assert len({item["id"] for item in chosen}) == 6
    _with_test_ranking(run)


def test_already_diverse_shelf_is_not_rewritten():
    def run():
        records = [
            _record("p1", "practical", 100, 90), _record("d1", "discover", 99, 89),
            _record("t1", "trend", 98, 88), _record("p2", "practical", 97, 87),
            _record("d2", "discover", 96, 86), _record("t2", "trend", 95, 85),
            _record("m1", "reflection", 10, 100),
        ]
        chosen, stretch = today._discover_pool(records, set(), limit=6)
        assert [item["id"] for item in chosen] == ["p1", "d1", "t1", "p2", "d2", "t2"]
        assert stretch is None
    _with_test_ranking(run)


def test_zero_one_and_action_exclusion_stay_safe():
    def run():
        assert today._discover_pool([], set()) == ([], None)
        chosen, stretch = today._discover_pool([_record("only", "trend", 1, 1)], set())
        assert [item["id"] for item in chosen] == ["only"] and stretch is None
        chosen, _ = today._discover_pool([_record("action", "practical", 9, 9), _record("other", "trend", 8, 8)], {"action"})
        assert [item["id"] for item in chosen] == ["other"]
    _with_test_ranking(run)
