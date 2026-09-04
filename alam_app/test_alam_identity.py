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


def test_queue_storage_repair_requests_one_rerun_for_stale_storage():
    current = "0f7f0d85-b58d-4d43-9042-76ef9f7464e8"
    stale = "4fd38a3b-95a3-4ac9-a888-a15fd11548a6"
    state = {}

    assert identity._queue_storage_repair(state, current, stale) is True
    assert state["alam_pending_device_storage"] == current

    # A browser write that remains pending after a component/storage failure must not
    # create an automatic rerun loop on every Streamlit render.
    assert identity._queue_storage_repair(state, current, stale) is False


def test_queue_storage_repair_skips_already_correct_or_invalid_identity():
    current = "0f7f0d85-b58d-4d43-9042-76ef9f7464e8"
    state = {}

    assert identity._queue_storage_repair(state, current, current) is False
    assert identity._queue_storage_repair(state, None, None) is False
    assert state == {}
