import json
from pathlib import Path

root = Path(__file__).resolve().parent
doc = json.loads((root / "data/questions.json").read_text(encoding="utf-8"))
qs = doc["questions"]
assert len(qs) == 650
assert len({q["id"] for q in qs}) == 650
assert all(q["question_en"] and isinstance(q["answer"], bool) and q["explanation"] for q in qs)
assert sum(bool(q.get("images")) for q in qs) == 133
for q in qs:
    for image in q.get("images", []):
        assert (root / image).is_file(), f"Missing image: {image}"
checks = {"KM15-Q033": True, "KM16-Q036": False, "KM16-Q048": False}
by_id = {q["id"]: q for q in qs}
for qid, expected in checks.items():
    assert by_id[qid]["answer"] is expected, qid
print("OK: 650 questions, 133 image questions, all linked images present, corrected answers preserved.")
