import base64
import zlib

import alam_action_checklist as checklist


def _record(step_action="Verify through the official channel"):
    return {
        "id": "story-1",
        "content": {
            "deadline": "Before September 30",
            "action_plan": {
                "goal": "Finish the verified process safely.",
                "steps": [
                    {
                        "step": "Verify eligibility",
                        "action": step_action,
                        "done_when": "The official channel confirms eligibility.",
                        "time_minutes": 5,
                    },
                    {
                        "step": "Submit",
                        "action": "Submit through the accepted official route.",
                        "done_when": "You have official acceptance evidence.",
                        "time_minutes": 10,
                    },
                ],
            },
        },
    }


def test_extracts_only_structured_action_plan_steps():
    plan = checklist.action_plan(_record())
    assert plan is not None
    assert plan["goal"] == "Finish the verified process safely."
    assert plan["deadline"] == "Before September 30"
    assert [step["title"] for step in plan["steps"]] == ["Verify eligibility", "Submit"]
    assert plan["steps"][0]["minutes"] == 5


def test_missing_or_unstructured_plan_fails_closed():
    assert checklist.action_plan({"id": "none", "content": {"action": "DO NOW"}}) is None
    assert checklist.action_plan({"id": "bad", "content": {"action_plan": {"steps": "not-a-list"}}}) is None


def test_invalid_and_duplicate_steps_are_removed():
    record = _record()
    first = dict(record["content"]["action_plan"]["steps"][0])
    record["content"]["action_plan"]["steps"] = [first, first, {"step": "Missing action"}, "bad"]
    plan = checklist.action_plan(record)
    assert plan is not None
    assert len(plan["steps"]) == 1


def test_materially_changed_action_gets_new_completion_identity():
    old_key = checklist.action_plan(_record())["steps"][0]["key"]
    new_key = checklist.action_plan(_record("Verify using the newly published official form"))["steps"][0]["key"]
    assert old_key != new_key


def test_cookie_codec_is_bounded_and_rejects_corruption():
    raw = {f"story-{i}": [f"step-{i}"] for i in range(checklist.MAX_STORIES + 5)}
    decoded = checklist._decode(checklist._encode(raw))
    assert len(decoded) == checklist.MAX_STORIES
    assert checklist._decode("corrupt-cookie") == {}

    oversized_json = b'{"story":["' + (b"x" * (checklist.MAX_COOKIE_JSON_BYTES + 256)) + b'"]}'
    bomb = base64.urlsafe_b64encode(zlib.compress(oversized_json, 9)).decode("ascii").rstrip("=")
    assert checklist._decode(bomb) == {}


def test_story_page_integrates_action_follow_through():
    from pathlib import Path

    source = (Path(__file__).resolve().parent / "alam_story_page.py").read_text(encoding="utf-8")
    assert "import alam_action_checklist as action_checklist" in source
    assert "action_checklist.render_action_checklist(record, manager)" in source
