import base64
import json
import zlib

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
