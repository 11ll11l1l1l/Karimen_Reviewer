import json

import alam_identity as identity


def test_component_ready_does_not_use_python_string_truthiness():
    assert identity._component_ready("false") is False
    assert identity._component_ready("0") is False
    assert identity._component_ready("true") is True
    assert identity._component_ready("1") is True


def test_parse_storage_result_keeps_false_ready_state_until_component_is_ready():
    device_id = "0f7f0d85-b58d-4d43-9042-76ef9f7464e8"
    raw = json.dumps({"ready": "false", "value": device_id, "error": None})

    ready, stored, error = identity._parse_storage_result(raw)

    assert ready is False
    assert stored == device_id
    assert error is None


def test_component_ready_invalid_shape_preserves_nonblocking_default():
    assert identity._component_ready({"unexpected": True}, True) is True
    assert identity._component_ready([False], False) is False
