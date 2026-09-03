import alam_action_checklist as checklist
import alam_today_page as today


def _record(story_id, title, second_minutes=10):
    second = {
        "step": "Submit",
        "action": "Submit through the accepted official route.",
        "done_when": "Official acceptance is recorded.",
    }
    if second_minutes is not None:
        second["time_minutes"] = second_minutes
    return {
        "id": story_id,
        "title": title,
        "content": {
            "action_plan": {
                "goal": "Complete the verified process.",
                "steps": [
                    {
                        "step": "Verify",
                        "action": "Verify through the official channel.",
                        "done_when": "Eligibility is confirmed.",
                        "time_minutes": 5,
                    },
                    second,
                ],
            }
        },
    }


def _progress_for(record, completed_indexes):
    plan = checklist.action_plan(record)
    return {
        checklist._story_key(record["id"]): [plan["steps"][index]["key"] for index in completed_indexes]
    }


def test_resume_lane_only_contains_genuinely_started_incomplete_plans():
    started = _record("started", "Started plan")
    untouched = _record("untouched", "Untouched plan")
    complete = _record("complete", "Complete plan")

    progress = {}
    progress.update(_progress_for(started, [0]))
    progress.update(_progress_for(complete, [0, 1]))

    items = today._resume_items([started, untouched, complete], progress=progress)

    assert [item["record"]["id"] for item in items] == ["started"]
    assert items[0]["done"] == 1
    assert items[0]["total"] == 2
    assert items[0]["focus"]["next"]["title"] == "Submit"
    assert items[0]["focus"]["remaining_minutes"] == 10


def test_resume_lane_prefers_most_recently_touched_story_and_is_bounded():
    old = _record("old", "Older plan")
    recent = _record("recent", "Recent plan")
    newest = _record("newest", "Newest plan")

    progress = {}
    progress.update(_progress_for(old, [0]))
    progress.update(_progress_for(recent, [0]))
    progress.update(_progress_for(newest, [0]))

    items = today._resume_items([old, recent, newest], progress=progress, limit=2)
    assert [item["record"]["id"] for item in items] == ["newest", "recent"]


def test_resume_lane_drops_stale_step_identity_after_material_change():
    original = _record("changed", "Changed instructions")
    progress = _progress_for(original, [0])

    changed = _record("changed", "Changed instructions")
    changed["content"]["action_plan"]["steps"][0]["action"] = "Verify through the newly published official form."

    assert today._resume_items([changed], progress=progress) == []


def test_resume_lane_does_not_guess_missing_remaining_effort():
    record = _record("unknown-time", "Unknown remaining time", second_minutes=None)
    items = today._resume_items([record], progress=_progress_for(record, [0]))

    assert len(items) == 1
    assert items[0]["focus"]["remaining_minutes"] is None


def test_resume_lane_handles_zero_and_unmatched_records():
    record = _record("missing", "Missing from current corpus")
    assert today._resume_items([], progress=_progress_for(record, [0])) == []
    assert today._resume_items([record], progress={}) == []
