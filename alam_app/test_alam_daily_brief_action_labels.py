"""Focused regression checks for decision-specific Today action labels."""

import alam_daily_brief as brief


def item(action=None):
    content = {} if action is None else {"action": action}
    return {"id": "x", "_category": "practical", "content": content}


def main():
    expected = {
        "DO NOW": ("DO NOW", "Open now"),
        "APPLY": ("APPLY", "Open application"),
        "AVOID": ("AVOID", "Open what to avoid"),
        "PREPARE": ("PREPARE", "Open preparation"),
        "BUY": ("BUY", "Open buying guidance"),
        "WAIT": ("WAIT", "Open why to wait"),
    }
    for action, (label, open_label) in expected.items():
        record = item(action)
        assert brief._display_label("DO", record) == label
        assert brief._brief_open_label("DO", record) == open_label

    # Never infer a decision from malformed or missing structured metadata.
    assert brief._display_label("DO", item("URGENT")) == "DO"
    assert brief._brief_open_label("DO", item("URGENT")) == "Open action"
    assert brief._display_label("DO", item()) == "DO"
    assert brief._display_label("WATCH", item("AVOID")) == "WATCH"
    print("ALAM Today decision-label regression checks passed")


if __name__ == "__main__":
    main()
