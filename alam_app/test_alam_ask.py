"""Regression tests for deterministic, evidence-only Ask ALAM retrieval."""

from alam_ask import grounded_answer, rank_records, relevance_score


VISA = {
    "id": "visa-fee",
    "_category": "practical",
    "title": "Japan visa renewal fees change in October",
    "summary": "Residence renewal costs rise from October.",
    "why_it_matters": "Foreign residents may pay more.",
    "tags": ["Japan", "Visa Renewal", "Immigration"],
    "importance": 98,
    "confidence": 99,
    "content": {
        "key_message": "File only when your residence application is genuinely ready.",
        "reading_levels": {"30 sec": {"bottom_line": "Check the official filing window."}},
    },
}

QUAKE = {
    "id": "quake-science",
    "_category": "discover",
    "title": "Japan maps earthquake plate locking more clearly",
    "summary": "Researchers combined seismic and deformation observations.",
    "tags": ["Earthquake", "Science"],
    "importance": 86,
    "confidence": 94,
    "content": {
        "key_message": "Better plate-locking maps are not an exact earthquake countdown."
    },
}



def test_relevant_record_ranks_first():
    ranked = rank_records([QUAKE, VISA], "visa renewal fee")
    assert ranked
    assert ranked[0][1]["id"] == "visa-fee"


def test_unrelated_high_quality_record_does_not_match():
    assert relevance_score(VISA, "penguin habitat antarctica") == 0
    assert rank_records([VISA, QUAKE], "penguin habitat antarctica") == []


def test_grounded_answer_reuses_record_text_exactly():
    answer = grounded_answer(QUAKE)
    assert answer == QUAKE["content"]["key_message"]
    assert "countdown" in answer


def test_quality_score_cannot_create_relevance():
    unrelated = dict(VISA)
    unrelated["importance"] = 100
    unrelated["confidence"] = 100
    assert relevance_score(unrelated, "ocean salinity") == 0


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"Ask ALAM retrieval regression passed ({len(tests)} tests)")
