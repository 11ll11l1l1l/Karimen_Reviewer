import base64
import json
import zlib
from types import SimpleNamespace

import alam_local_state as local_state


def _encoded_payload(raw_bytes, suffix=b""):
    packed = zlib.compress(raw_bytes, 9) + suffix
    return base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")


def _assert_decode_rejected(code):
    try:
        local_state._decode(code)
    except (ValueError, zlib.error):
        return
    raise AssertionError("unsafe profile payload was accepted")


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
    profile["b"] = {"bookmark-good": 20, "bookmark-bad": {"minute": 420}}

    encoded = local_state._encode(profile)
    decoded = local_state._decode(encoded)
    trimmed = local_state._trim(decoded)

    assert trimmed["r"] == {"read-good": 10, "read-bad": 0}
    assert trimmed["b"] == {"bookmark-good": 20}


def test_profile_decoder_rejects_oversized_encoded_input_before_base64_decode(monkeypatch):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Base64 decoder should not run for oversized input")

    monkeypatch.setattr(local_state.base64, "urlsafe_b64decode", fail_if_called)

    _assert_decode_rejected("A" * (local_state.MAX_PROFILE_CODE_CHARS + 1))
    assert called is False


def test_profile_decoder_rejects_oversized_decompressed_json():
    raw = json.dumps(
        {"v": local_state.COOKIE_VERSION, "s": {"blob": "x" * local_state.MAX_PROFILE_JSON_BYTES}},
        separators=(",", ":"),
    ).encode("utf-8")
    assert len(raw) > local_state.MAX_PROFILE_JSON_BYTES

    _assert_decode_rejected(_encoded_payload(raw))


def test_profile_decoder_rejects_trailing_bytes_after_valid_zlib_stream():
    valid = json.dumps(local_state._default_profile(), separators=(",", ":")).encode("utf-8")

    _assert_decode_rejected(_encoded_payload(valid, b"trailing-junk"))


def test_profile_alert_threshold_normalizes_corrupt_and_out_of_range_values():
    assert local_state._profile_alert_min("92") == 92
    assert local_state._profile_alert_min({"bad": "shape"}) == 85
    assert local_state._profile_alert_min(999) == 100
    assert local_state._profile_alert_min(-4) == 0


def test_restored_profile_booleans_do_not_use_python_string_truthiness(monkeypatch):
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(local_state, "st", fake_streamlit)
    profile = local_state._default_profile()
    profile["s"] = {
        "interests": {"Japan": "false", "Family": "1", "AI": 0},
        "alert_action": "false",
        "alert_change": "0",
        "dark": "true",
    }

    local_state._apply_settings(profile)

    assert fake_streamlit.session_state["alam_interest_preferences"] == {
        "Japan": False,
        "Family": True,
        "AI": False,
    }
    assert fake_streamlit.session_state["alam_alert_only_actionable"] is False
    assert fake_streamlit.session_state["alam_alert_material_change"] is False
    assert fake_streamlit.session_state["alam_dark_mode"] is True


def test_profile_boolean_normalizer_falls_back_for_invalid_shapes():
    assert local_state._profile_bool(True, False) is True
    assert local_state._profile_bool(False, True) is False
    assert local_state._profile_bool({"bad": "shape"}, False) is False
    assert local_state._profile_bool([1], True) is True
