import alam_local_state as local_state


def test_trim_drops_only_corrupt_persisted_timestamps():
    profile = local_state._default_profile()
    profile["r"] = {
        "valid-int": 120,
        "valid-string": "240",
        "bad-text": "not-a-minute",
        "bad-object": {"minute": 300},
    }
    profile["b"] = {
        "saved-valid": "360",
        "saved-bad": [420],
    }
    profile["s"] = {"dark": True}

    trimmed = local_state._trim(profile)

    assert trimmed["r"] == {"valid-string": 240, "valid-int": 120}
    assert trimmed["b"] == {"saved-valid": 360}
    assert trimmed["s"] == {"dark": True}


def test_corrupt_timestamp_entries_do_not_break_cookie_profile_normalization():
    profile = local_state._default_profile()
    profile["r"] = {"read-good": 10, "read-bad": None, "read-worse": "NaN"}
    profile["b"] = {"bookmark-good": 20, "bookmark-bad": object()}

    encoded = local_state._encode(profile)
    decoded = local_state._decode(encoded)
    trimmed = local_state._trim(decoded)

    assert trimmed["r"] == {"read-good": 10, "read-bad": 0}
    assert trimmed["b"] == {"bookmark-good": 20}
