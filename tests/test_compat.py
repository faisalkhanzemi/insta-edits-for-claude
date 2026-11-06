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
