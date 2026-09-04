import hashlib

import alam_local_state as local_state


def _token(prefix, index, length):
    return hashlib.sha256(f"{prefix}-{index}".encode("utf-8")).hexdigest()[:length]


def test_cookie_profile_stays_within_browser_budget_without_dropping_saved_snapshots():
    profile = local_state._default_profile()
    profile["r"] = {
        _token("read", index, 12): 30_000_000 - index
        for index in range(local_state.MAX_READ)
    }
    profile["m"] = [
        _token("mute", index, 12)
        for index in range(local_state.MAX_MUTED)
    ]
    profile["f"] = {
        _token("feedback", index, 12): [
            "IMPORTANT",
            "discover",
            [_token(f"topic-{index}", topic, 16) for topic in range(4)],
        ]
        for index in range(local_state.MAX_FEEDBACK)
    }
    profile["b"] = {
        _token("bookmark", index, 12): 30_000_000 - index
        for index in range(local_state.MAX_SAVED_SNAPSHOTS)
    }
    profile["s"] = {
        "interests": {f"topic-{index}": bool(index % 2) for index in range(12)},
        "alert_min": 85,
        "alert_action": False,
        "alert_change": True,
        "dark": False,
    }

    trimmed = local_state._trim(profile)
    assert len(local_state._encode(trimmed)) > local_state.MAX_COOKIE_VALUE_CHARS

    fitted = local_state._fit_cookie_profile(profile)

    assert len(local_state._encode(fitted)) <= local_state.MAX_COOKIE_VALUE_CHARS
    assert fitted["s"] == trimmed["s"]
    assert fitted["b"] == trimmed["b"]
    assert len(fitted["r"]) < len(trimmed["r"])
