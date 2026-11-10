import json

from insta_edits import compat


def test_drops_invalid_cache_scope_and_missing_ttl():
    msg = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "a"}], "cacheScope": "session"}}
    fixed = compat.fix_message(msg)
    assert fixed["result"] == {"tools": [{"name": "a"}]}
    assert msg["result"]["cacheScope"] == "session", "input must not be mutated"


def test_drops_non_numeric_ttl():
    fixed = compat.fix_message({"id": 2, "result": {"tools": [], "cacheScope": "public", "ttlMs": "60s"}})
    assert fixed["result"] == {"tools": []}


def test_keeps_valid_hints():
    msg = {"id": 3, "result": {"tools": [], "cacheScope": "private", "ttlMs": 5000}}
    assert compat.fix_message(msg) == msg


def test_bool_is_not_a_valid_ttl():
    assert compat.cache_hint_problems({"cacheScope": "public", "ttlMs": True})


def test_passes_through_errors_notifications_and_non_dicts():
    error = {"id": 4, "error": {"code": -1, "message": "x"}}
    note = {"method": "notifications/tools/list_changed"}
    assert compat.fix_message(error) == error
    assert compat.fix_message(note) == note
    assert compat.fix_message([1, 2]) == [1, 2]


def test_problems_are_described():
    problems = compat.cache_hint_problems({"cacheScope": "session"})
    assert any("cacheScope='session'" in p for p in problems)
    assert any("ttlMs missing" in p for p in problems)


def test_drops_complete_result_type_without_cache_fields():
    msg = {"id": 5, "result": {"tools": [], "resultType": "complete", "_meta": {"x": 1}}}
    assert compat.fix_message(msg)["result"] == {"tools": [], "_meta": {"x": 1}}


def test_keeps_complete_result_type_with_valid_cache_fields():
    msg = {"id": 6, "result": {"tools": [], "resultType": "complete", "ttlMs": 1000, "cacheScope": "public"}}
    assert compat.fix_message(msg) == msg


def test_keeps_other_result_types():
    msg = {"id": 7, "result": {"resultType": "task", "taskId": "t1"}}
    assert compat.fix_message(msg) == msg


def _tool_result(payload):
    return {"jsonrpc": "2.0", "id": 9, "result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}


def test_speed_catalog_points_at_set_speed_curve():
    caps = {
        "catalogs": [
            {"kind": "filter", "applyTool": "applyFilter"},
            {"kind": "speedCurvePreset", "applyTool": "selectSpeedPanelPreset", "applyParam": "preset"},
        ]
    }
    msg = _tool_result(caps)
    fixed = json.loads(compat.fix_message(msg)["result"]["content"][0]["text"])
    assert fixed["catalogs"][1] == {"kind": "speedCurvePreset", "applyTool": "setSpeedCurve", "applyParam": "preset"}
    assert fixed["catalogs"][0] == {"kind": "filter", "applyTool": "applyFilter"}
    assert "selectSpeedPanelPreset" in msg["result"]["content"][0]["text"], "input must not be mutated"


def test_speed_catalog_item_and_structured_content_are_fixed():
    item = {"ok": True, "item": {"kind": "speedCurvePreset", "id": "HERO", "applyTool": "selectSpeedPanelPreset"}}
    msg = _tool_result(item)
    msg["result"]["structuredContent"] = item
    fixed = compat.fix_message(msg)["result"]
    assert json.loads(fixed["content"][0]["text"])["item"]["applyTool"] == "setSpeedCurve"
    assert fixed["structuredContent"]["item"]["applyTool"] == "setSpeedCurve"


def test_other_mentions_of_the_speed_tool_pass_through():
    # A tool that merely names selectSpeedPanelPreset (not as a speed catalog's applyTool) is left alone,
    # and so is text that isn't JSON.
    note = _tool_result({"kind": "filter", "applyTool": "selectSpeedPanelPreset"})
    assert compat.fix_message(note) == note
    plain = {"id": 4, "result": {"content": [{"type": "text", "text": "selectSpeedPanelPreset is deprecated"}]}}
    assert compat.fix_message(plain) == plain
